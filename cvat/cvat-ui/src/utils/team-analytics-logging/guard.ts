// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Every entry point of the logging module runs through `guarded`: a failure never reaches the caller,
// which gets the fallback instead, and after MAX_FAILURES failures the module switches itself off for
// the rest of the page's life (every entry point then returns its fallback without trying).

export const MAX_FAILURES = 3;

let failures = 0;

export function switchedOff(): boolean {
    return failures >= MAX_FAILURES;
}

export function recordFailure(error?: unknown): void {
    failures += 1;
    try {
        console.warn('Team analytics logging failed', error);
    } catch {
        // nothing to do
    }
}

export function guarded<T>(fallback: T, work: () => T): T {
    if (switchedOff()) return fallback;
    try {
        return work();
    } catch (error: unknown) {
        recordFailure(error);
        return fallback;
    }
}
