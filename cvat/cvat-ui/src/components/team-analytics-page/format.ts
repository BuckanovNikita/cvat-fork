// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

const HOUR_MS = 3600000;

// Hours as the page shows them: one decimal, whole hours from 1,000 h on.
export function formatHours(ms: number): string {
    const hours = ms / HOUR_MS;
    if (hours >= 1000) {
        return `${Math.round(hours).toLocaleString('en-US')} h`;
    }
    return `${hours.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} h`;
}

// A length of time: seconds under a minute, minutes under an hour, then hours.
export function formatDuration(ms: number): string {
    if (ms < 60000) {
        return `${Math.round(ms / 1000)} s`;
    }
    if (ms < HOUR_MS) {
        return `${Math.round(ms / 60000)} min`;
    }
    return formatHours(ms);
}

// A project as the page names it: No project for id 0, CVAT's name when CVAT returns the project to
// the viewer, otherwise its identifier (e.g. a deleted project stays in past figures).
export function projectName(id: number, names: Record<number, string>): string {
    if (id === 0) return 'No project';
    return names[id] ?? `Project #${id}`;
}

// The exact value, for hover text.
export function exactHours(ms: number): string {
    return `${(ms / HOUR_MS).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} h`;
}
