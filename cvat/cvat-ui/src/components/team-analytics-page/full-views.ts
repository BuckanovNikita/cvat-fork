// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The full view open on the page, kept in the address (`view`; `rows=projects` for a chart that switches
// between annotators and projects), so that Back and a shared link behave as expected. Part of `Address`
// (address.ts), which owns reading and writing the address. No `view` = the overview.

export const TREND_VIEWS = {
    'trend-working_time': 'working_time',
    'trend-boxes': 'boxes',
    'trend-average': 'average',
    'trend-hotkey_share': 'hotkey_share',
} as const;

export const FULL_VIEWS = [
    'time', 'split', 'operations', 'methods', 'projects', 'annotators', 'hotkeys',
    ...Object.keys(TREND_VIEWS) as (keyof typeof TREND_VIEWS)[],
] as const;

export type FullView = typeof FULL_VIEWS[number];
export type FullViewRows = 'annotators' | 'projects';

// the full views whose rows switch between annotators and projects
export const SWITCHABLE: FullView[] = ['split', 'operations', 'methods'];

export interface FullViewAddress {
    view?: FullView | null;
    rows?: FullViewRows;
}

export function readFullView(search: string): Required<FullViewAddress> {
    const query = new URLSearchParams(search);
    const view = FULL_VIEWS.find((key) => key === query.get('view')) ?? null;
    return { view, rows: query.get('rows') === 'projects' ? 'projects' : 'annotators' };
}

// The query string for the full view, keeping every other key of `search`; nothing is written for the
// overview, so its address stays as it was.
export function fullViewSearch(address: FullViewAddress, search: string): string {
    const query = new URLSearchParams(search);
    if (address.view) query.set('view', address.view);
    else query.delete('view');
    if (address.view && SWITCHABLE.includes(address.view) && address.rows === 'projects') query.set('rows', 'projects');
    else query.delete('rows');
    const text = query.toString();
    return text ? `?${text}` : '';
}

// The trend metric a trend full view shows (see trends.ts `trendMetrics`), or null for another view.
export function trendOfView(view: FullView | null | undefined): string | null {
    return view && view in TREND_VIEWS ? TREND_VIEWS[view as keyof typeof TREND_VIEWS] : null;
}

export function viewOfTrend(metric: string): FullView {
    const found = Object.entries(TREND_VIEWS).find(([, key]) => key === metric);
    return (found ? found[0] : 'trend-working_time') as FullView;
}
