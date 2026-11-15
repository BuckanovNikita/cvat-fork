"""Judges a render as the objects Kubernetes would create from it (run.sh guard_render).

stdin: the render as kubectl reads it, a stream of JSON objects from
`kubectl label --local -f RENDER -o json` (kubectl parses every document, YAML or JSON, and
flattens a List into its items). The cluster's resource list (`kubectl api-resources
--no-headers`) is read from --resources.

Refused, each named on stderr:
- an object whose (API group, kind) the cluster does not list as namespaced: a cluster-wide
  kind, a kind the cluster does not know (a custom resource of a definition not installed),
  or a List left unflattened;
- an object whose metadata.namespace is set to another namespace than --namespace;
- an `image` field anywhere in an object that is not a string, or names an image that is not
  on the --allow list, or has no tag or the tag `latest` (Kubernetes pulls those by default);
- an `imagePullPolicy` anywhere other than IfNotPresent or Never;
- with --backend IMAGE: any image of IMAGE's repository other than IMAGE, or IMAGE absent;
- these ways to the host or the outside, and only these: a Service of a type other than
  ClusterIP (unset, or headless with clusterIP None, is ClusterIP) or with external IPs; and,
  as keys at any depth of any object, host networking, host PID or host IPC, a host port, a
  host path volume, privileged mode and added capabilities (a key of that name elsewhere, such
  as a ConfigMap data key `hostPath`, is refused too: a false refusal, kept);
- what reaches other projects' storage or routes, by allowlist (what the genuine render uses is
  allowed, nothing else): a volume of a pod, at any depth, with a source other than configMap,
  emptyDir, persistentVolumeClaim or projected, or a projected source other than configMap; a
  `volumeName` anywhere (a claim that names a volume); any Ingress (the stack has none: its
  address is the proxy behind a port-forward); an Endpoints or EndpointSlice object, which the
  genuine render does not contain (the cluster writes them for Services with a selector); a
  Secret of a type other than unset, Opaque or generic (a service account token Secret);
- a RoleBinding whose role is a ClusterRole, or with a subject other than a ServiceAccount of
  --namespace;
- a render with no object;
- with --analytics on: no Team Analytics worker, i.e. no Deployment labelled
  component=worker-team-analytics whose container runs `run worker team_analytics`; with
  --analytics off: any object labelled component=worker-team-analytics.

Not refused: the rest of a container's security settings (`allowPrivilegeEscalation: true` among them), and anything else the checks
above do not name. The host checks (Service type, host fields, privileged mode,
capabilities) and the role binding checks still refuse by list.

On success prints the render's images, normalised and sorted, one per line. Exit 0 accepted,
1 refused, 2 unreadable input. Standard library only.
"""

import argparse
import json
import sys
from collections.abc import Iterator

ALLOWED_PULL_POLICIES = {"IfNotPresent", "Never"}
# the volume sources the genuine render (chart and proxy) uses, and the sources inside a projected one
ALLOWED_VOLUME_SOURCES = {"configMap", "emptyDir", "persistentVolumeClaim", "projected"}
ALLOWED_PROJECTED_SOURCES = {"configMap"}
# the cluster writes these for a Service with a selector; written by hand they send a Service anywhere
ENDPOINT_KINDS = {("", "Endpoints"), ("discovery.k8s.io", "EndpointSlice")}
# the Secret types of the genuine render (unset is Opaque; the chart writes "generic" for three)
ALLOWED_SECRET_TYPES = {None, "Opaque", "generic"}


def normalize(image: str) -> str:
    """Docker Hub's implicit prefixes removed, as docker image inspect names the image."""
    for prefix in ("docker.io/", "index.docker.io/"):
        if image.startswith(prefix):
            image = image[len(prefix) :]
    if image.startswith("library/"):
        image = image[len("library/") :]
    return image


def split_reference(image: str) -> tuple[str, str | None, str | None]:
    """(repository, tag, digest); the tag is read from the last path segment, so a registry
    port is not taken for one."""
    digest = None
    if "@" in image:
        image, digest = image.split("@", 1)
    head, _, last = image.rpartition("/")
    tag = None
    if ":" in last:
        last, tag = last.split(":", 1)
    return (f"{head}/{last}" if head else last), tag, digest


def read_objects(text: str) -> Iterator[object]:
    decoder = json.JSONDecoder()
    i = 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return
        obj, i = decoder.raw_decode(text, i)
        yield obj


def read_resources(path: str) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(namespaced, cluster-wide) sets of (API group, kind), from the right-hand columns of
    `kubectl api-resources --no-headers`: APIVERSION NAMESPACED KIND."""
    namespaced: set[tuple[str, str]] = set()
    cluster: set[tuple[str, str]] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            cols = line.split()
            if len(cols) < 4:
                continue
            api_version, scoped, kind = cols[-3], cols[-2], cols[-1]
            key = (group_of(api_version), kind)
            (namespaced if scoped == "true" else cluster).add(key)
    return namespaced, cluster


def group_of(api_version: str) -> str:
    return api_version.rpartition("/")[0] if "/" in api_version else ""


def image_fields(node: object, path: str) -> Iterator[tuple[str, object, object]]:
    """(path of the holder, image value, sibling imagePullPolicy) for every `image` key at any
    depth, and (path, None, policy) for a pull policy without an image beside it."""
    if isinstance(node, dict):
        if "image" in node:
            yield path, node["image"], node.get("imagePullPolicy")
        elif "imagePullPolicy" in node:
            yield path, None, node["imagePullPolicy"]
        for key, value in node.items():
            yield from image_fields(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from image_fields(value, f"{path}[{index}]")


def host_reach(node: object, path: str) -> Iterator[str]:
    """What in a pod spec or security context reaches the host, at any depth, so that a template
    nested in a Deployment, a Job or a CronJob is judged as a Pod is."""
    if isinstance(node, dict):
        for key in ("hostNetwork", "hostPID", "hostIPC"):
            if node.get(key) not in (None, False):
                yield f"{key} at {path}.{key}"
        if node.get("hostPort") not in (None, 0):
            yield f"host port at {path}.hostPort: {node['hostPort']}"
        if "hostPath" in node:
            yield f"host path volume at {path}.hostPath"
        if node.get("privileged") not in (None, False):
            yield f"privileged mode at {path}.privileged"
        capabilities = node.get("capabilities")
        if isinstance(capabilities, dict) and capabilities.get("add"):
            yield f"added capabilities at {path}.capabilities.add: {capabilities['add']}"
        for key, value in node.items():
            yield from host_reach(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from host_reach(value, f"{path}[{index}]")


def storage(node: object, path: str) -> Iterator[str]:
    """Volumes with a source the genuine render does not use, and claims that name a volume, at any depth."""
    if isinstance(node, dict):
        if "volumeName" in node:
            yield f"claim naming a volume at {path}.volumeName: {node['volumeName']}"
        if "volumes" in node:
            volumes = node["volumes"]
            for index, volume in enumerate(volumes if isinstance(volumes, list) else [volumes]):
                where = f"{path}.volumes[{index}]"
                if not isinstance(volume, dict):
                    yield f"volume that is not an object at {where}"
                    continue
                for source, value in volume.items():
                    if source == "name":
                        continue
                    if source not in ALLOWED_VOLUME_SOURCES:
                        yield f"volume source not on the list at {where}.{source}"
                    elif source == "projected":
                        sources = value.get("sources") if isinstance(value, dict) else None
                        for i, item in enumerate(sources if isinstance(sources, list) else [sources]):
                            kinds = set(item) if isinstance(item, dict) else {"?"}
                            if not kinds <= ALLOWED_PROJECTED_SOURCES:
                                yield f"projected source not on the list at {where}.projected.sources[{i}]: {sorted(kinds)}"
        for key, value in node.items():
            yield from storage(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from storage(value, f"{path}[{index}]")


def reach(obj: dict, name: str, namespace: str) -> Iterator[str]:
    """Services that reach outside the cluster, host access, and role bindings that grant more than the
    namespace's own roles to more than the namespace's own service accounts."""
    kind = obj.get("kind")
    spec = obj.get("spec") if isinstance(obj.get("spec"), dict) else {}
    if kind == "Service":
        if spec.get("type", "ClusterIP") != "ClusterIP":
            yield f"Service reaching the host or the outside: {name} of type {spec.get('type')}"
        if spec.get("externalIPs"):
            yield f"Service with external IPs: {name}"
    if kind == "RoleBinding":
        role = obj.get("roleRef") if isinstance(obj.get("roleRef"), dict) else {}
        if role.get("kind") != "Role":
            yield f"role binding to a cluster-wide role: {name} binds {role.get('kind')}/{role.get('name')}"
        subjects = obj.get("subjects") or []
        for subject in subjects if isinstance(subjects, list) else [subjects]:
            if not isinstance(subject, dict) or subject.get("kind") != "ServiceAccount" \
                    or subject.get("namespace") not in (None, "", namespace):
                yield f"role binding to a subject outside {namespace}: {name} binds {subject}"
    if kind == "Ingress":
        yield f"Ingress (the stack routes through its own proxy only): {name}"
    if (group_of(str(obj.get("apiVersion", ""))), kind) in ENDPOINT_KINDS:
        yield f"endpoints written by hand: {name}"
    if kind == "Secret" and group_of(str(obj.get("apiVersion", ""))) == "" \
            and obj.get("type") not in ALLOWED_SECRET_TYPES:
        yield f"Secret of a type not on the list: {name} of type {obj.get('type')}"
    yield from host_reach(obj, name)
    yield from storage(obj, name)


def judge(
    objects: list[object],
    namespace: str,
    namespaced: set[tuple[str, str]],
    cluster: set[tuple[str, str]],
    allowed: set[str],
    backend: str | None,
    analytics: str | None = None,
) -> tuple[list[str], set[str]]:
    problems: list[str] = []
    images: set[str] = set()
    backend_repo = split_reference(normalize(backend))[0] if backend else None
    backend_seen = False
    if not objects:
        problems.append("the render holds no object")
    for obj in objects:
        if not isinstance(obj, dict):
            problems.append(f"not an object: {str(obj)[:60]}")
            continue
        kind = str(obj.get("kind", ""))
        api_version = str(obj.get("apiVersion", ""))
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        name = f"{kind}/{metadata.get('name', '?')}"
        key = (group_of(api_version), kind)
        if key in cluster:
            problems.append(f"cluster-wide kind in render: {name} ({api_version})")
        elif key not in namespaced:
            problems.append(f"kind the cluster does not list as namespaced: {name} ({api_version})")
        object_namespace = metadata.get("namespace")
        if object_namespace not in (None, "", namespace):
            problems.append(f"object in another namespace than {namespace}: {name} in {object_namespace}")
        problems.extend(reach(obj, name, namespace))
        for path, image, policy in image_fields(obj, name):
            if policy is not None and policy not in ALLOWED_PULL_POLICIES:
                problems.append(f"pull policy {policy!r} at {path}.imagePullPolicy")
            if image is None:
                continue
            if not isinstance(image, str) or not image:
                problems.append(f"image field that is not an image name at {path}.image")
                continue
            ref = normalize(image.strip())
            images.add(ref)
            repo, tag, digest = split_reference(ref)
            if tag is None and digest is None or tag == "latest":
                problems.append(f"image Kubernetes pulls by default (no tag or latest) at {path}.image: {image}")
            if ref not in allowed:
                problems.append(f"image not on the stack's list at {path}.image: {image}")
            if backend_repo is not None and repo == backend_repo:
                if ref == normalize(backend or ""):
                    backend_seen = True
                else:
                    problems.append(f"server image other than the fork server image at {path}.image: {image}")
    if backend and not backend_seen:
        problems.append(f"the fork server image {backend} is not in the render")
    if analytics is not None:
        problems.extend(analytics_worker(objects, analytics == "on"))
    return problems, images


WORKER_COMPONENT = "worker-team-analytics"
WORKER_ARGS = ["run", "worker", "team_analytics"]


def analytics_worker(objects: list[object], enabled: bool) -> Iterator[str]:
    """The Team Analytics worker of the chart (templates/cvat_backend/worker_team_analytics): present and
    running its queue when analytics is enabled, absent when it is not."""
    labelled = [
        obj for obj in objects
        if isinstance(obj, dict) and isinstance(obj.get("metadata"), dict)
        and (obj["metadata"].get("labels") or {}).get("component") == WORKER_COMPONENT
    ]
    if not enabled:
        for obj in labelled:
            yield f"Team Analytics worker in a render with analytics off: {obj.get('kind')}/{obj['metadata'].get('name')}"
        return
    workers = [
        obj for obj in labelled
        if obj.get("kind") == "Deployment"
        and any(c.get("args") == WORKER_ARGS
                for c in (((obj.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers") or [])
    ]
    if len(workers) != 1:
        yield f"expected one Team Analytics worker Deployment running {' '.join(WORKER_ARGS)}, found {len(workers)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--resources", required=True, help="output of kubectl api-resources --no-headers")
    parser.add_argument("--allow", nargs="*", default=[], help="images the render may name")
    parser.add_argument("--backend", help="the only image of its repository allowed in the render")
    parser.add_argument("--analytics", choices=("on", "off"),
                        help="whether the render must hold the Team Analytics worker (on) or must not (off)")
    args = parser.parse_args()
    try:
        objects = list(read_objects(sys.stdin.read()))
    except json.JSONDecodeError as exc:
        print(f"refused: the render is not readable as objects: {exc}", file=sys.stderr)
        return 2
    namespaced, cluster = read_resources(args.resources)
    if ("", "Pod") not in namespaced or ("apiextensions.k8s.io", "CustomResourceDefinition") not in cluster:
        print("refused: the cluster's resource list is incomplete", file=sys.stderr)
        return 2
    allowed = {normalize(a) for a in args.allow}
    problems, images = judge(objects, args.namespace, namespaced, cluster, allowed, args.backend, args.analytics)
    for problem in problems:
        print(f"refused: {problem}", file=sys.stderr)
    if problems:
        return 1
    for image in sorted(images):
        print(image)
    return 0


if __name__ == "__main__":
    sys.exit(main())
