// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The project and annotator filters as kept in the page address (`project`, `annotator`: identifiers;
// project 0 = No project). Part of `Address` (address.ts), which owns reading and writing the address.
//
// Identifiers mean something only inside one organization, so the address also names the organization
// the filters were picked in (`org`, the slug; absent = no organization, i.e. instance scope). Filters
// whose organization is not the current one (after an organization switch, or a link shared from
// another organization) are not applied.

export interface Filters {
    project: number | null;
    annotator: number | null;
}

const IDENTIFIER = /^\d{1,15}$/;
const ORGANIZATION = 'org';

function readId(value: string | null): number | null {
    return value !== null && IDENTIFIER.test(value) ? Number(value) : null;
}

export function readFilters(search: string, organization: string | null = null): Filters {
    const query = new URLSearchParams(search);
    if ((query.get(ORGANIZATION) || null) !== (organization || null)) return { project: null, annotator: null };
    return { project: readId(query.get('project')), annotator: readId(query.get('annotator')) };
}

// The query string for `filters` picked in `organization`, keeping every other key of `search`.
export function filtersSearch(filters: Filters, search: string, organization: string | null = null): string {
    const query = new URLSearchParams(search);
    for (const key of ['project', 'annotator'] as const) {
        const value = filters[key];
        if (value === null || value === undefined) query.delete(key);
        else query.set(key, String(value));
    }
    const filtered = query.has('project') || query.has('annotator');
    if (filtered && organization) query.set(ORGANIZATION, organization);
    else query.delete(ORGANIZATION);
    const text = query.toString();
    return text ? `?${text}` : '';
}
