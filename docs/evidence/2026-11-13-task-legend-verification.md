# Task legend verification — 2026-11-13

## Report and source identity

The reported task card on another machine contained task `18594`, owner
`cvat.prod`, and `• 1 annotation / new • 1 total`. The stage/state text was
reported to have the same pale yellow color as the progress bar.

Application source inspected: `13b2ea4`, including text-color fix `001eb38`.
Fetching `origin` confirmed that `origin/main` already contained `001eb38`.
The specification commit `13b2ea4` was still local at that point.

The text-color fix removes the palette's inline color from the legend while
keeping the segment background. Independent source review found no remaining
palette-color assignment to this legend in task-card or global styles. A stale
image/container on the other machine is plausible, but was not verified there.

## Browser regression

Added an optional browser check to `verify/task_progress.cjs`. It renders the
actual `TaskJobsProgress` component using real Ant Design generated styles and
the compiled task-card stylesheet, with a single annotation/new job for task
`18594`. An isolated headless Chrome profile computes the nested text color,
card background and bar color. The test asserts at least 4.5:1 text contrast.
The temporary profile and fixture are removed after the check.

Command:

```bash
BROWSER_BIN=google-chrome node --test verify/task_progress.cjs
```

All 21 checks passed, including the browser check. The original 20 checks use
mocked application/API boundaries; the additional check uses a real browser
with a local component fixture, not the deployed application.

UI type checking also passed with
`node node_modules/typescript/bin/tsc -p cvat-ui/tsconfig.json` from `cvat/`.
The `yarn run type-check` launcher was unavailable on this host, so the same
installed TypeScript compiler and project configuration were invoked directly.
Independent review of the integrated test and documentation found no actionable
issues; no additional application-code change was needed.

The historical component from `c56f2d0` was temporarily substituted to verify
that the new browser check detects the reported failure. It failed specifically
on unreadable text. The current component was restored and its blob hash was
verified before the passing full-suite run.

| Component | Browser-computed text | Bar background | Text contrast on white |
| --- | --- | --- | --- |
| Before `001eb38` | `rgb(250, 251, 177)` | `rgb(250, 251, 177)` | 1.08:1 — fails |
| Current | `rgba(0, 0, 0, 0.88)` | `rgb(250, 251, 177)` | 16.56:1 — passes |

## Previously built artifact, re-inspected

The image built earlier in this conversation from the same application source
was inspected again. Its compiled legend has no inline color; only the segment
uses the palette background. Application source was unchanged by this follow-up,
so the successful production build was reused rather than repeated.

- Image: `cvat/ui:v2.82.0-progress-colors-readable-text-001eb38`, `linux/amd64`.
- Image ID: `sha256:1dd784ccd52a830914395e34151b70f61919e25e99b33fc446a26c0a0351e3cf`.
- Main asset: `assets/cvat-ui.f37663d05dc15228282b.min.js`.
- Transfer archive: `cvat-ui-v2.82.0-progress-colors-readable-text-001eb38.tar.gz`.
- Archive SHA-256: `09c097dc8e2cfc48a83db11511661ab739ff136bae5e7685bfb6bc798056b6a8`.

The earlier production build completed with peer/optional canvas warnings and
two webpack size warnings. The image's nginx configuration check passed with an
inherited duplicate MIME-type warning. Inspection containers were automatically
removed. The image/archive is a local build output, not part of the Git commit.

## Limits

No access to the other machine's browser, loaded image or task API was provided.
This proves local component color behavior and the packaged code, not that the
remote deployment serves it. The browser fixture does not exercise the complete
task page, authentication, backend permissions or live job retrieval. Replacing
the image on that machine still requires recreating its UI container using the
intended image tag and its existing Compose configuration.
