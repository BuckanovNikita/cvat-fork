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

export const MISSING = '—';

// Time per operation: seconds, one decimal under ten.
export function formatSeconds(ms: number | null): string {
    if (ms === null) return MISSING;
    const seconds = ms / 1000;
    return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds).toLocaleString('en-US')} s`;
}

export function formatCount(value: number): string {
    return Math.round(value).toLocaleString('en-US');
}

// A count shortened for a tile: 1.23M from a million, 123K from a hundred thousand.
export function shortCount(value: number): string {
    if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e5) return `${Math.round(value / 1000)}K`;
    return formatCount(value);
}

// A share of a whole, rounded to a percent.
export function formatShare(share: number | null): string {
    return share === null ? MISSING : `${Math.round(share * 100)}%`;
}

// A project as the page names it: No project for id 0, its name when the project still exists, otherwise its
// identifier (e.g. a deleted project stays in past figures).
export function projectName(id: number, names: Record<number, string>): string {
    if (id === 0) return 'No project';
    return names[id] ?? `Project #${id}`;
}

// The exact value, for hover text.
export function exactHours(ms: number): string {
    return `${(ms / HOUR_MS).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} h`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];

// 'YYYY-MM-DD' (a calendar day the service names) -> 'Nov 7'. Read from its parts, so the zone the
// browser runs in cannot move it.
export function dayLabel(day: string, withYear = false): string {
    const [year, month, date] = day.split('-').map(Number);
    return `${MONTHS[month - 1]} ${date}${withYear ? `, ${year}` : ''}`;
}

// 'YYYY-MM' -> 'November 2026'.
export function monthLabel(month: string): string {
    const [year, number] = month.split('-').map(Number);
    return `${MONTH_NAMES[number - 1]} ${year}`;
}
