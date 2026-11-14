// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The page's state kept in its address (query string of /team-analytics), so that Back and a shared
// link behave as expected. One place reads and writes it: add a field to `Address`, read it in
// `readAddress` and write it in `addressSearch`. Keys this module does not know are left as they are.
// A user's change is a new history entry; reading never rewrites the address (a bad value falls back).

import {
    useCallback, useEffect, useMemo, useState,
} from 'react';

import { Filters, filtersSearch, readFilters } from './filters';
import { Shapes, readShapes, shapesSearch } from './shapes';
import { FullViewAddress, fullViewSearch, readFullView } from './full-views';

export const PERIODS = [
    { key: 'week', label: 'Week' },
    { key: 'two_weeks', label: 'Two weeks' },
    { key: 'month', label: 'Month' },
    { key: 'year', label: 'Year' },
] as const;

export type PeriodKey = typeof PERIODS[number]['key'];

// project and annotator filters: see filters.ts
// the open full view (full-views.ts) is optional: an address without it is the overview
export interface Address extends Filters, FullViewAddress {
    period: PeriodKey;
    // YYYY-MM when the period is a month, otherwise null
    month: string | null;
    // the Bounding boxes / All shapes switch (shapes.ts)
    shapes: Shapes;
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

// `organization` is the one CVAT has selected (null = none): filters of another one are not read.
export function readAddress(search: string, now: Date = new Date(), organization: string | null = null): Address {
    const query = new URLSearchParams(search);
    const period = PERIODS.find(({ key }) => key === query.get('period'))?.key ?? 'week';
    const filters = { ...readFilters(search, organization), shapes: readShapes(search), ...readFullView(search) };
    if (period !== 'month') return { period, month: null, ...filters };
    const latest = currentMonth(now);
    const month = query.get('month') ?? '';
    // YYYY-MM strings compare in calendar order
    return { period, month: MONTH.test(month) && month <= latest ? month : latest, ...filters };
}

// The query string for `address`, keeping every key of `search` this module does not own.
export function addressSearch(address: Address, search: string, organization: string | null = null): string {
    const others = shapesSearch(address.shapes, fullViewSearch(address, search));
    const query = new URLSearchParams(filtersSearch(address, others, organization));
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
export function useAddress(
    history: AddressHistory,
    organization: string | null = null,
): [Address, (change: Partial<Address>) => void] {
    const [search, setSearch] = useState(history.location?.search ?? '');
    useEffect(() => (history.listen ? history.listen((location) => setSearch(location.search)) : undefined), [history]);
    const address = useMemo(() => readAddress(search, new Date(), organization), [search, organization]);
    const change = useCallback((next: Partial<Address>): void => {
        const merged = { ...address, ...next };
        if (next.period === 'month' && !next.month) merged.month = currentMonth();
        // the selection already shown (also when the address only implies it) is not a new entry
        const keys = Object.keys(merged) as (keyof Address)[];
        if (keys.every((key) => merged[key] === address[key])) return;
        const current = history.location?.search ?? search;
        const nextSearch = addressSearch(merged, current, organization);
        if (nextSearch === current) return;
        history.push({ ...(history.location ?? {}), search: nextSearch });
        if (!history.listen) setSearch(nextSearch);
    }, [address, history, search, organization]);
    return [address, change];
}
