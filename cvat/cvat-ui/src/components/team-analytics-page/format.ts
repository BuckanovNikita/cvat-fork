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

// The exact value, for hover text.
export function exactHours(ms: number): string {
    return `${(ms / HOUR_MS).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} h`;
}
