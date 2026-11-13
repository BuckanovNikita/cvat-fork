// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The project and annotator filters, kept in the page address (`project`, `annotator`: identifiers;
// project 0 = No project) so that Back and a shared link behave as expected. Keys this module does
// not own are left as they are. A change is a new history entry; reading never rewrites the address.

import { useCallback, useEffect, useMemo, useState } from 'react';

export interface Filters {
    project: number | null;
    annotator: number | null;
}

const IDENTIFIER = /^\d{1,15}$/;

function readId(value: string | null): number | null {
    return value !== null && IDENTIFIER.test(value) ? Number(value) : null;
}

export function readFilters(search: string): Filters {
    const query = new URLSearchParams(search);
    return { project: readId(query.get('project')), annotator: readId(query.get('annotator')) };
}

// The query string for `filters`, keeping every key of `search` this module does not own.
export function filtersSearch(filters: Filters, search: string): string {
    const query = new URLSearchParams(search);
    for (const key of ['project', 'annotator'] as const) {
        const value = filters[key];
        if (value === null) query.delete(key);
        else query.set(key, String(value));
    }
    const text = query.toString();
    return text ? `?${text}` : '';
}

interface FilterHistory {
    location?: { search: string };
    listen?: (listener: (location: { search: string }) => void) => () => void;
    push(location: { search: string } | string): void;
}

// The filters as state: follows Back and Forward, and records a change as a new history entry.
export function useFilters(history: FilterHistory): [Filters, (change: Partial<Filters>) => void] {
    const [search, setSearch] = useState(history.location?.search ?? '');
    useEffect(() => (history.listen ? history.listen((location) => setSearch(location.search)) : undefined), [history]);
    const filters = useMemo(() => readFilters(search), [search]);
    const change = useCallback((next: Partial<Filters>): void => {
        const current = history.location?.search ?? search;
        const nextSearch = filtersSearch({ ...readFilters(current), ...next }, current);
        if (nextSearch === current) return;
        history.push({ ...(history.location ?? {}), search: nextSearch });
        if (!history.listen) setSearch(nextSearch);
    }, [history, search]);
    return [filters, change];
}
