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
