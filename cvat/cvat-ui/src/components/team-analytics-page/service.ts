// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The page's only boundary to the analytics service. Tests replace `fetchService`.

export const TEAM_ANALYTICS_PATH = '/team-analytics';
export const SERVICE_PREFIX = '/team-analytics-api/v1/';

export interface AnnotatorWorkingTime {
    user_id: number;
    user_name: string;
    working_time_ms: number;
}

// The period a response covers, as the service echoes it (days are the viewer's calendar days).
export interface Period {
    name: string;
    first_day: string; // YYYY-MM-DD
    last_day: string; // YYYY-MM-DD
    month: string | null; // YYYY-MM for a month
    to_date: boolean;
    unit: 'day' | 'week';
}

export interface TimeSeries {
    unit: 'day' | 'week';
    buckets: { start: string; working_time_ms: number }[]; // start: YYYY-MM-DD
}

export interface SessionFigures {
    sessions: number;
    average_ms: number;
    total_ms: number;
}

export interface AnnotatorSessions extends SessionFigures {
    user_id: number;
    user_name: string;
}

export interface ProjectWorkingTime {
    project_id: number; // 0 = No project
    working_time_ms: number;
}

// the rows a chart does not show: how many and their working time
export interface Rest {
    count: number;
    working_time_ms: number;
}

// the project and annotator filters the figures were read with (project 0 = No project)
export interface AppliedFilters {
    project: number | null;
    annotator: { user_id: number; user_name: string | null } | null;
}

// project id -> name as CVAT returns it to the viewer; a project missing here is shown by its id
export type ProjectNames = Record<number, string>;

export interface Overview {
    period?: Period;
    // the eight largest rows (project filter applied) and the rest
    by_annotator: { rows: AnnotatorWorkingTime[]; rest?: Rest };
    time_series?: TimeSeries;
    // the eight largest rows (annotator filter applied) and the rest
    by_project?: { rows: ProjectWorkingTime[]; rest: Rest };
    // active annotators within the scope and both filters, and the projects they worked in
    headline?: { annotators: number; projects: number };
    filters?: AppliedFilters;
    // the scope's figures plus the same per annotator (most sessions first)
    sessions?: SessionFigures & { by_annotator: AnnotatorSessions[] };
}

// GET status; each key is one status section of the service.
export interface Status {
    refresh?: {
        last_success_at: string | null; // ISO time of the last successful refresh
        now: string; // the service's time
        interval_s: number;
        stale_after_s: number;
        stale: boolean;
    };
}

export type PageState =
    | { kind: 'loading' }
    | { kind: 'ready'; overview: Overview }
    | { kind: 'denied' }
    | { kind: 'select-organization' }
    | { kind: 'signed-out' }
    | { kind: 'error' };

export interface ServiceResponse {
    ok: boolean;
    status: number;
    json(): Promise<any>;
}

export type FetchService = (url: string, init: RequestInit) => Promise<ServiceResponse>;

export const fetchService: FetchService = (url, init) => window.fetch(url, init);

export interface OverviewQuery {
    // slug of the organization selected in CVAT, null for none
    organization: string | null;
    timeZone: string;
    // the page address's period and month (see address.ts); Week when not given
    period?: string;
    month?: string | null;
    // the page's filters (see filters.ts); project 0 = No project
    project?: number | null;
    annotator?: number | null;
}

export function viewerTimeZone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
}

async function body(response: ServiceResponse): Promise<any> {
    try {
        return await response.json();
    } catch {
        return null;
    }
}

function serviceParams(query: OverviewQuery): URLSearchParams {
    const params = new URLSearchParams({
        org: query.organization ?? '',
        period: query.period ?? 'week',
        tz: query.timeZone,
    });
    if (query.month) params.set('month', query.month);
    if (query.project !== null && query.project !== undefined) params.set('project', String(query.project));
    if (query.annotator !== null && query.annotator !== undefined) params.set('annotator', String(query.annotator));
    return params;
}

// The status of the figures, or null when it cannot be read (the page then shows no freshness).
export async function loadStatus(query: OverviewQuery, fetch: FetchService = fetchService): Promise<Status | null> {
    const params = new URLSearchParams({ org: query.organization ?? '' });
    try {
        const response = await fetch(`${SERVICE_PREFIX}status?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        const data = await body(response);
        return response.ok && data ? data as Status : null;
    } catch {
        return null;
    }
}

export async function loadOverview(query: OverviewQuery, fetch: FetchService = fetchService): Promise<PageState> {
    const params = serviceParams(query);
    let response: ServiceResponse;
    try {
        response = await fetch(`${SERVICE_PREFIX}overview?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
    } catch {
        return { kind: 'error' };
    }
    const data = await body(response);
    if (response.ok && data && data.by_annotator) {
        return { kind: 'ready', overview: data as Overview };
    }
    if (response.status === 403 && data?.error === 'organization_required') {
        return { kind: 'select-organization' };
    }
    if (response.status === 401) {
        return { kind: 'signed-out' };
    }
    if (response.status === 403) {
        return { kind: 'denied' };
    }
    return { kind: 'error' };
}
