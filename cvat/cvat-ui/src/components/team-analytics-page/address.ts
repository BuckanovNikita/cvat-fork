// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The page's state kept in its address (query string of /team-analytics), so that Back and a shared
// link behave as expected. One place reads and writes it: add a field to `Address`, read it in
// `readAddress` and write it in `addressSearch`. Keys this module does not know are left as they are.
// A user's change is a new history entry; reading never rewrites the address (a bad value falls back).

import { useCallback, useEffect, useMemo, useState } from 'react';

export const PERIODS = [
    { key: 'week', label: 'Week' },
    { key: 'two_weeks', label: 'Two weeks' },
    { key: 'month', label: 'Month' },
    { key: 'year', label: 'Year' },
] as const;

export type PeriodKey = typeof PERIODS[number]['key'];

export interface Address {
    period: PeriodKey;
    // YYYY-MM when the period is a month, otherwise null
    month: string | null;
}

const pad = (value: number): string => String(value).padStart(2, '0');

// The viewer's current month (the browser's own zone, which the page also sends to the service).
export function currentMonth(now: Date = new Date()): string {
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

export function shiftMonth(month: string, delta: number): string {
    const [year, number] = month.split('-').map(Number);
    const index = year * 12 + (number - 1) + delta;
    return `${Math.floor(index / 12)}-${pad((index % 12) + 1)}`;
}

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

export function readAddress(search: string, now: Date = new Date()): Address {
    const query = new URLSearchParams(search);
    const period = PERIODS.find(({ key }) => key === query.get('period'))?.key ?? 'week';
    if (period !== 'month') return { period, month: null };
    const latest = currentMonth(now);
    const month = query.get('month') ?? '';
    // YYYY-MM strings compare in calendar order
    return { period, month: MONTH.test(month) && month <= latest ? month : latest };
}

// The query string for `address`, keeping every key of `search` this module does not own.
export function addressSearch(address: Address, search: string): string {
    const query = new URLSearchParams(search);
    query.set('period', address.period);
    if (address.period === 'month' && address.month) query.set('month', address.month);
    else query.delete('month');
    const text = query.toString();
    return text ? `?${text}` : '';
}

interface AddressHistory {
    location?: { search: string };
    listen?: (listener: (location: { search: string }) => void) => () => void;
    push(location: { search: string } | string): void;
}

// The address as state: follows Back and Forward, and records a change as a new history entry.
export function useAddress(history: AddressHistory): [Address, (change: Partial<Address>) => void] {
    const [search, setSearch] = useState(history.location?.search ?? '');
    useEffect(() => (history.listen ? history.listen((location) => setSearch(location.search)) : undefined), [history]);
    const address = useMemo(() => readAddress(search), [search]);
    const change = useCallback((next: Partial<Address>): void => {
        const merged = { ...address, ...next };
        if (next.period === 'month' && !next.month) merged.month = currentMonth();
        const current = history.location?.search ?? search;
        const nextSearch = addressSearch(merged, current);
        if (nextSearch === current) return;
        history.push({ ...(history.location ?? {}), search: nextSearch });
        if (!history.listen) setSearch(nextSearch);
    }, [address, history, search]);
    return [address, change];
}
