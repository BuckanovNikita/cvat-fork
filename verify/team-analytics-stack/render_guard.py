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
- a render with no object.

On success prints the render's images, normalised and sorted, one per line. Exit 0 accepted,
1 refused, 2 unreadable input. Standard library only.
"""

import argparse
import json
import sys
from collections.abc import Iterator

ALLOWED_PULL_POLICIES = {"IfNotPresent", "Never"}


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


def judge(
    objects: list[object],
    namespace: str,
    namespaced: set[tuple[str, str]],
    cluster: set[tuple[str, str]],
    allowed: set[str],
    backend: str | None,
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
    return problems, images


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--resources", required=True, help="output of kubectl api-resources --no-headers")
    parser.add_argument("--allow", nargs="*", default=[], help="images the render may name")
    parser.add_argument("--backend", help="the only image of its repository allowed in the render")
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
    problems, images = judge(objects, args.namespace, namespaced, cluster, allowed, args.backend)
    for problem in problems:
        print(f"refused: {problem}", file=sys.stderr)
    if problems:
        return 1
    for image in sorted(images):
        print(image)
    return 0


if __name__ == "__main__":
    sys.exit(main())
