// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The project and annotator filters as kept in the page address (`project`, `annotator`: identifiers;
// project 0 = No project). Part of `Address` (address.ts), which owns reading and writing the address.

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

// The query string for `filters`, keeping every other key of `search`.
export function filtersSearch(filters: Filters, search: string): string {
    const query = new URLSearchParams(search);
    for (const key of ['project', 'annotator'] as const) {
        const value = filters[key];
        if (value === null || value === undefined) query.delete(key);
        else query.set(key, String(value));
    }
    const text = query.toString();
    return text ? `?${text}` : '';
}
