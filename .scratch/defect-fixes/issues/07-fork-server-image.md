# 07: Fork server image

**What to build:** One script builds the fork server image: the stock release image with the two patched policies copied over the stock ones, and nothing else. See ADR 0004 and "Policies and the fork server image" in the spec (`../spec.md`).

**Blocked by:** 06 (Policies patched in place with the role floor).

**Status:** ready-for-agent

- [ ] A build script beside the UI's builds the image from the stock release image and the two patched policies of the import. Nothing is installed and no Python changes.
- [ ] The image's tag names the release and marks it as the fork's. Its default is set in the script, as for the UI image.
- [ ] The server's own bundle builder, run in the image with no mounts, yields a bundle whose two policies equal the patched files of the import. The same check on the stock image shows the stock policies.
- [ ] Compared with the stock image, only those two files differ.
- [ ] The script needs no network when the stock image is local, and never pulls or pushes.
- [ ] The Team Analytics service image still builds on the stock base, unchanged.
- [ ] The checks are recorded in a dated evidence file.
