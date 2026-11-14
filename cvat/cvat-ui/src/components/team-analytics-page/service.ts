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

export type OperationName = 'creation' | 'alignment' | 'class_change' | 'deletion' | 'other';

export interface OperationRow {
    operation: OperationName;
    // objects the operation touched (alignment: alignments); 0 for Other
    objects: number;
    timed_objects: number;
    time_ms: number;
    // time per object with a measured time; null when none was measured
    average_ms: number | null;
    // of operations + Other; null when there is no time at all
    share: number | null;
    // objects of operations started by hotkey / by mouse (neither when the method was not recorded)
    hotkey_objects?: number;
    mouse_objects?: number;
}

// Keyboard and mouse use in the scope. Hotkeys are named by action; the page labels them.
export interface InputFigures {
    hotkey_actions: number;
    // clicks on controls (the canvas is left out)
    mouse_actions: number;
    canvas_clicks: number;
    // hotkey actions of hotkey and mouse actions; null when there were none
    hotkey_share: number | null;
    // the most used hotkeys (most first) and the rest
    top_hotkeys: { action: string; actions: number }[];
    rest: { count: number; actions: number };
}

export interface OperationsFigures {
    // the scope has no shape-tagged event in the period
    legacy: boolean;
    // the shapes the figures cover: the switch asked for, or all shapes in a legacy period
    shapes?: 'bounding_boxes' | 'all';
    working_time_ms: number;
    // operations + Other, the denominator of every share
    active_time_ms: number;
    // creation, alignment, class change, deletion and other, in that order
    rows: OperationRow[];
}

export type CreationMethodName = 'drawn' | 'pasted' | 'propagated';

export interface CreationMethodRow {
    method: CreationMethodName;
    objects: number;
    timed_objects: number;
    time_ms: number;
    // time per object with a measured time; null when none was measured
    average_ms: number | null;
    // of the objects of the three methods; null when there are none
    share: number | null;
}

// The Creation operation split by method: the rows add up to it and `total.average_ms` is its average.
export interface CreationMethods {
    shapes?: 'bounding_boxes' | 'all';
    // drawn, pasted and propagated, in that order
    rows: CreationMethodRow[];
    total: { objects: number; timed_objects: number; time_ms: number; average_ms: number | null };
    // Model: objects no person drew (saved by technical accounts, made by the built-in detector), counts only,
    // outside the three and their total; share of the three + Model
    model?: { objects: number; share: number | null };
    // how many accounts are configured as technical
    technical_accounts?: number;
}

// Single-frame rectangles the server stored when jobs were saved, whatever their creation method
export interface SavedBoxes {
    boxes: number;
    // technical accounts left out; most boxes first
    by_annotator: { user_id: number; user_name: string; boxes: number }[];
    // every method; most boxes first (project 0 = No project)
    by_project: { project_id: number; boxes: number }[];
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
    operations?: OperationsFigures;
    input?: InputFigures;
    creation_methods?: CreationMethods;
    saved_boxes?: SavedBoxes;
    // false: the period is not wholly processed, so the figures are partial and are not shown
    processed?: boolean;
}

// How far history is processed (status section `history`), in the viewer's time zone.
export interface HistoryStatus {
    complete: boolean;
    ready_from: string | null; // ISO time from which everything is processed; null when complete or nothing is
    ready_from_day: string | null; // YYYY-MM-DD: the viewer's first whole processed day
    first_day: string | null; // YYYY-MM-DD: the first day with events
    days_ready: number;
    days_total: number;
    periods: Record<string, boolean>; // period key -> wholly processed
    earliest_month: string | null; // YYYY-MM: the earliest wholly processed month (null: none, or all when complete)
    complete_weeks: number;
    trends_ready: boolean;
}

// GET status; each key is one status section of the service.
export interface Status {
    history?: HistoryStatus | null;
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
    // the Bounding boxes / All shapes switch (see shapes.ts)
    shapes?: 'bounding_boxes' | 'all';
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
    if (query.shapes) params.set('shapes', query.shapes);
    return params;
}

// --- refusals: the page state for a 401 or 403 from any endpoint ---------------------------------------------

export type RefusedState = { kind: 'denied' } | { kind: 'select-organization' } | { kind: 'signed-out' };

export function refusalOf(response: ServiceResponse, data: any): RefusedState | null {
    if (response.status === 403 && data?.error === 'organization_required') return { kind: 'select-organization' };
    if (response.status === 401) return { kind: 'signed-out' };
    if (response.status === 403) return { kind: 'denied' };
    return null;
}

type RefusalListener = (state: RefusedState) => void;
const refusalListeners = new Set<RefusalListener>();

// The page listens here: a refusal of the trends, details, list or status request (a loader then answers
// null, like a failure) replaces the whole page with the refusal, as one of the overview does.
export function onRefusal(listener: RefusalListener): () => void {
    refusalListeners.add(listener);
    return () => { refusalListeners.delete(listener); };
}

function reportRefusal(response: ServiceResponse, data: any): void {
    const refusal = refusalOf(response, data);
    if (refusal) refusalListeners.forEach((listener) => listener(refusal));
}

// The status of the figures, or null when it cannot be read (the page then shows no freshness).
export async function loadStatus(query: OverviewQuery, fetch: FetchService = fetchService): Promise<Status | null> {
    const params = new URLSearchParams({ org: query.organization ?? '', tz: query.timeZone });
    try {
        const response = await fetch(`${SERVICE_PREFIX}status?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        const data = await body(response);
        reportRefusal(response, data);
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
    return refusalOf(response, data) ?? { kind: 'error' };
}

// --- trends (GET trends): twelve weeks or months, independent of the period --------------------------------

export type TrendStep = 'week' | 'month';
export type CompareKind = 'annotators' | 'projects';

// One week or month of one line. Creation figures are null where the shapes cannot be told apart (a bucket
// before the new logging under Bounding boxes); hotkey share is null when there were no actions to share.
export interface TrendPoint {
    working_time_ms: number;
    // the line had job work in the bucket and none of it was shape-tagged
    legacy: boolean;
    boxes: number | null;
    timed_boxes: number | null;
    box_time_ms: number | null;
    average_ms: number | null;
    // false: before the new logging, hotkey use was not recorded
    hotkey_recorded: boolean;
    hotkey_actions: number;
    mouse_actions: number;
    hotkey_share: number | null;
}

export interface TrendLine {
    // null for the scope's own line; otherwise the compared annotator's or project's id
    id: number | null;
    user_name: string | null;
    points: TrendPoint[]; // one per bucket
}

export interface Trends {
    step: TrendStep;
    shapes: 'bounding_boxes' | 'all';
    compare: CompareKind;
    // first day of each week (Monday) or month; an unprocessed bucket's figures are partial and not shown
    buckets: { start: string; processed: boolean }[];
    lines: TrendLine[];
    // everyone of the compared kind with work in the twelve buckets (most working time first)
    candidates: { id: number; user_name: string | null; working_time_ms: number }[];
}

export interface TrendsQuery {
    organization: string | null;
    timeZone: string;
    project: number | null;
    annotator: number | null;
    shapes: 'bounding_boxes' | 'all';
    step: TrendStep;
    compare: CompareKind;
    ids: number[];
}

// The trends, or null when they cannot be read (the trends card then says so).
export async function loadTrends(query: TrendsQuery, fetch: FetchService = fetchService): Promise<Trends | null> {
    const params = new URLSearchParams({
        org: query.organization ?? '',
        tz: query.timeZone,
        shapes: query.shapes,
        step: query.step,
        compare: query.compare,
    });
    if (query.project !== null) params.set('project', String(query.project));
    if (query.annotator !== null) params.set('annotator', String(query.annotator));
    if (query.ids.length) params.set('ids', query.ids.join(','));
    try {
        const response = await fetch(`${SERVICE_PREFIX}trends?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        const data = await body(response);
        reportRefusal(response, data);
        const readable = response.ok && !!data && Array.isArray(data.buckets) && Array.isArray(data.lines) &&
            Array.isArray(data.candidates) && data.lines.every(
                (line: TrendLine) => Array.isArray(line?.points) && line.points.length === data.buckets.length,
            );
        return readable ? data as Trends : null;
    } catch {
        return null;
    }
}

// --- full view lists (GET list): every row of one chart ----------------------------------------------------

export type ListKind = 'annotators' | 'projects' | 'hotkeys';

export interface ListFigures {
    objects: number;
    timed_objects: number;
    time_ms: number;
    // time per object with a measured time; null when none was measured
    average_ms: number | null;
}

// One annotator or project of a full view
export interface ListRow {
    id: number; // project 0 = No project
    user_name: string | null; // annotators only
    working_time_ms: number;
    // of all rows' working time; null when there is none
    share: number | null;
    operations: Record<'creation' | 'alignment' | 'class_change' | 'deletion', ListFigures> & {
        other: { time_ms: number };
    };
    methods: Record<CreationMethodName, ListFigures>;
    // objects no person drew: detector boxes, and for a project also what technical accounts saved
    model: number;
}

export interface HotkeyListRow {
    action: string;
    actions: number;
    share: number; // of all hotkey actions
}

export interface RowsList {
    by: 'annotators' | 'projects';
    period?: Period;
    // false: the period is not wholly processed, so the figures are partial and are not shown
    processed?: boolean;
    legacy: boolean;
    shapes: 'bounding_boxes' | 'all';
    total: { count: number; working_time_ms: number };
    rows: ListRow[];
}

export interface HotkeysList {
    by: 'hotkeys';
    period?: Period;
    processed?: boolean;
    hotkey_actions: number;
    rows: HotkeyListRow[];
}

export type FullList = RowsList | HotkeysList;

// Every row of one chart for a full view, or null when the list cannot be read (the full view says so).
export async function loadList(
    query: OverviewQuery & { by: ListKind }, fetch: FetchService = fetchService,
): Promise<FullList | null> {
    const params = serviceParams(query);
    params.set('by', query.by);
    try {
        const response = await fetch(`${SERVICE_PREFIX}list?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        const data = await body(response);
        reportRefusal(response, data);
        const readable = response.ok && !!data && data.by === query.by && Array.isArray(data.rows);
        return readable ? data as FullList : null;
    } catch {
        return null;
    }
}

// --- details (GET details): the paged, searchable table by annotator or by project ------------------------------

export type DetailsKind = 'annotators' | 'projects';

// Every figure of one annotator or one project in the period. `projects` (annotator rows) / `annotators`
// (project rows) count the other dimension. Model per annotator is the built-in detector only; saved boxes
// replace it in a legacy period.
export interface DetailsRow {
    id: number; // user id, or project id (0 = No project)
    user_name: string | null;
    projects?: number;
    annotators?: number;
    sessions: number;
    working_time_ms: number;
    drawn: number;
    pasted: number;
    propagated: number;
    model: number;
    saved_boxes: number;
    alignments: number;
    class_changes: number;
    deletions: number;
    average_create_ms: number | null;
    hotkey_share: number | null;
}

export interface Details {
    by: DetailsKind;
    page: number; // 1-based, the page actually shown
    page_size: number;
    total: number; // rows matching the search
    legacy: boolean;
    shapes: 'bounding_boxes' | 'all';
    processed?: boolean;
    technical_accounts?: number;
    rows: DetailsRow[];
    // projects only: every project in the table before the search, for finding projects by name
    project_ids?: number[];
}

export interface DetailsQuery extends OverviewQuery {
    by: DetailsKind;
    page: number;
    // annotators: text the name contains
    search?: string;
    // projects: the ids whose shown name matches (an empty list matches none); null = no search
    ids?: number[] | null;
}

// The details table, or null when it cannot be read (the table then says so).
export async function loadDetails(query: DetailsQuery, fetch: FetchService = fetchService): Promise<Details | null> {
    const params = serviceParams(query);
    params.set('by', query.by);
    params.set('page', String(query.page));
    if (query.search) params.set('search', query.search);
    if (query.ids) params.set('ids', query.ids.join(','));
    try {
        const response = await fetch(`${SERVICE_PREFIX}details?${params}`, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        const data = await body(response);
        reportRefusal(response, data);
        const readable = response.ok && !!data && Array.isArray(data.rows) && typeof data.total === 'number';
        return readable ? data as Details : null;
    } catch {
        return null;
    }
}
