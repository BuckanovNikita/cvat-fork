// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The page's only boundary to Team Analytics: CVAT's own API at `<backendAPI>/team-analytics/` (the figures, the
// project names and the settings), asked through cvat-core. Tests replace `requestService` and `requestSettings`.

import { getCore, ServerError } from 'cvat-core-wrapper';

export const TEAM_ANALYTICS_PATH = '/team-analytics';
// the API path under cvat-core's API root (`core.config.backendAPI`, '/api')
export const SERVICE_PATH = 'team-analytics';

export interface AnnotatorWorkingTime {
    user_id: number;
    user_name: string;
    working_time_ms: number;
    // the row's operation parts, equal to its row in the full view
    operations?: RowOperations;
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
    // the period ends before the cutover to the new activity logging (the first shape-tagged event on the
    // instance, or none yet) and the scope has job work in it
    legacy: boolean;
    // the cutover falls inside the period: bounding box figures, class changes and hotkey use cover the days since
    partly_legacy?: boolean;
    // the cutover (ISO), or null before there is one
    cutover?: string | null;
    // the shapes the figures cover: the switch asked for, or all shapes in a legacy period
    shapes?: 'bounding_boxes' | 'all';
    // the figures below are null in a period not wholly processed (the flags above stay)
    working_time_ms: number | null;
    // operations + Other, the denominator of every share
    active_time_ms: number | null;
    // creation, alignment, class change, deletion and other, in that order
    rows: OperationRow[] | null;
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
    // the row's operation parts, equal to its row in the full view
    operations?: RowOperations;
}

// the rows a chart does not show: how many, their working time and their operation parts added up
export interface Rest {
    count: number;
    working_time_ms: number;
    operations?: RowOperations;
}

// The rows of working time by annotator or by project: the largest and the rest. `legacy` is the full view's flag
// for these rows (the overview's own `operations.legacy` applies both filters, these rows only the other one).
export interface WorkingTimeRows<Row> {
    legacy?: boolean;
    rows: Row[];
    rest?: Rest;
}

// the project and annotator filters the figures were read with (project 0 = No project)
export interface AppliedFilters {
    project: number | null;
    annotator: { user_id: number; user_name: string | null } | null;
}

// project id -> name (GET project-names); a project missing here (deleted) is shown by its id
export type ProjectNames = Record<number, string>;

// In a period not wholly processed (`processed: false`) the service sends no figures: every section but
// `period`, `filters` and the legacy flags of `operations` is null. The page shows why instead of any card.
export interface Overview {
    period?: Period;
    // the eight largest rows (project filter applied) and the rest
    by_annotator: WorkingTimeRows<AnnotatorWorkingTime> | null;
    time_series?: TimeSeries | null;
    // the eight largest rows (annotator filter applied) and the rest
    by_project?: WorkingTimeRows<ProjectWorkingTime> | null;
    // active annotators within the scope and both filters, and the projects they worked in
    headline?: { annotators: number; projects: number } | null;
    filters?: AppliedFilters;
    // the scope's figures plus the same per annotator (most sessions first)
    sessions?: (SessionFigures & { by_annotator: AnnotatorSessions[] }) | null;
    operations?: OperationsFigures;
    input?: InputFigures | null;
    creation_methods?: CreationMethods | null;
    saved_boxes?: SavedBoxes | null;
    // false: the period is not wholly processed, so it carries no figures
    processed?: boolean;
}

// How far history is processed (status section `history`), in the viewer's time zone. The fields marked
// "whole instance" describe the whole instance whatever the scope (only administrators read the status).
export interface HistoryStatus {
    complete: boolean;
    percent?: number; // whole percent of the days with events that are processed; 100 only when complete
    // whole instance. ISO time from which everything is processed; null when complete or nothing is
    ready_from?: string | null;
    ready_from_day?: string | null; // whole instance. YYYY-MM-DD: the viewer's first whole processed day
    first_day?: string | null; // whole instance. YYYY-MM-DD: the first day with events
    days_ready?: number; // whole instance
    days_total?: number; // whole instance
    periods: Record<string, boolean>; // period key -> wholly processed
    earliest_month: string | null; // YYYY-MM: the earliest wholly processed month (null: none, or all when complete)
    complete_weeks: number;
    trends_ready: boolean;
}

// GET status; each key is one status section of the service.
export interface Status {
    history?: HistoryStatus | null;
    // the cutover to the new activity logging: the first shape-tagged event on the instance (ISO), or null
    cutover?: { at: string | null } | null;
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
    | { kind: 'signed-out' }
    | { kind: 'error' };

// The figures' endpoints and the fork's lookups (project names; the settings are asked through requestSettings)
export type Endpoint =
    | 'status' | 'overview' | 'trends' | 'list' | 'details' | 'project-names' | 'settings/users';

// An HTTP answer of the API: its status and its body (null when there is none the page can read).
export interface ServiceAnswer {
    status: number;
    body: any;
    // for a refusal or failure: the text cvat-core made of the error body (a 400's `detail` sentence)
    message?: string;
}

// Asks one endpoint with the given query parameters. Answers every HTTP answer, a refusal or failure too;
// throws only when there is no answer at all (CVAT unreachable, a timeout).
export type RequestService = (endpoint: Endpoint, params: Record<string, string>) => Promise<ServiceAnswer>;

export const requestService: RequestService = async (endpoint, params) => {
    const core = getCore();
    try {
        // cvat-core attaches the current organization as `org`; the page sends none of its own
        // the Axios response (cvat-core's `serverRequest`)
        const response = await core.server.request(`${core.config.backendAPI}/${SERVICE_PATH}/${endpoint}`, {
            method: 'GET',
            params,
        }) as { status: number; data: unknown };
        return { status: response.status, body: response.data ?? null };
    } catch (error) {
        // a ServerError without an HTTP status (code 0: no response, a timeout) is no answer at all
        if (error instanceof ServerError && error.code >= 100) {
            return { status: error.code, body: null };
        }
        throw error;
    }
};

function succeeded(answer: ServiceAnswer): boolean {
    return answer.status >= 200 && answer.status < 300;
}

export interface OverviewQuery {
    // slug of the organization selected in CVAT, null for none. Not sent: cvat-core attaches the current
    // organization to every request; the page keys its requests and its address by it.
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

// The query parameters of the period, filters and shapes. The organization is not one of them: cvat-core
// attaches the current one, and the page keeps `query.organization` only for its own address and state.
function serviceParams(query: OverviewQuery): Record<string, string> {
    const params: Record<string, string> = {
        period: query.period ?? 'week',
        tz: query.timeZone,
    };
    if (query.month) params.month = query.month;
    if (query.project !== null && query.project !== undefined) params.project = String(query.project);
    if (query.annotator !== null && query.annotator !== undefined) params.annotator = String(query.annotator);
    if (query.shapes) params.shapes = query.shapes;
    return params;
}

// --- refusals: the page state for a 401, 403 or 404 from any endpoint -----------------------------------------

export type RefusedState = { kind: 'denied' } | { kind: 'signed-out' };

// Team Analytics is for administrators only: every 403 is the "denied" state. A 404 (analytics switched off on
// the server, or an unknown organization) reads as "not available" too. Any other failure, a 429 that outlived
// cvat-core's retries too, is no refusal: the loaders' error.
export function refusalOf(answer: ServiceAnswer): RefusedState | null {
    if (answer.status === 401) return { kind: 'signed-out' };
    if (answer.status === 403 || answer.status === 404) return { kind: 'denied' };
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

function reportRefusal(answer: ServiceAnswer): void {
    const refusal = refusalOf(answer);
    if (refusal) refusalListeners.forEach((listener) => listener(refusal));
}

// The status of the figures, or null when it cannot be read (the page then shows no freshness).
export async function loadStatus(
    query: OverviewQuery, request: RequestService = requestService,
): Promise<Status | null> {
    try {
        const answer = await request('status', { tz: query.timeZone });
        reportRefusal(answer);
        return succeeded(answer) && answer.body ? answer.body as Status : null;
    } catch {
        return null;
    }
}

export async function loadOverview(
    query: OverviewQuery, request: RequestService = requestService,
): Promise<PageState> {
    let answer: ServiceAnswer;
    try {
        answer = await request('overview', serviceParams(query));
    } catch {
        return { kind: 'error' };
    }
    const data = answer.body;
    // an answer without figures (a period not wholly processed) is a ready one too: the page says why
    if (succeeded(answer) && data && (data.by_annotator || data.processed === false)) {
        return { kind: 'ready', overview: data as Overview };
    }
    return refusalOf(answer) ?? { kind: 'error' };
}

// --- trends (GET trends): twelve weeks or months, independent of the period --------------------------------

export type TrendStep = 'week' | 'month';
export type CompareKind = 'annotators' | 'projects';

// One week or month of one line. Creation figures are null where the shapes cannot be told apart (a bucket
// before the new logging under Bounding boxes); hotkey share is null when there were no actions to share.
// In a bucket not wholly processed every value is null and only `legacy` and `hotkey_recorded` are sent.
export interface TrendPoint {
    working_time_ms: number | null;
    // the line had job work in the bucket and the bucket ends before the cutover to the new logging
    legacy: boolean;
    boxes: number | null;
    timed_boxes: number | null;
    box_time_ms: number | null;
    average_ms: number | null;
    // false: before the new logging, hotkey use was not recorded
    hotkey_recorded: boolean;
    hotkey_actions: number | null;
    mouse_actions: number | null;
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
    // first day of each week (Monday) or month; a bucket not wholly processed has no figures
    buckets: { start: string; processed: boolean }[];
    lines: TrendLine[];
    // everyone of the compared kind with work in the twelve buckets, most working time first; the working time
    // counts only processed buckets and is null while none is (then the order is by id)
    candidates: { id: number; user_name: string | null; working_time_ms: number | null }[];
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
export async function loadTrends(
    query: TrendsQuery, request: RequestService = requestService,
): Promise<Trends | null> {
    const params: Record<string, string> = {
        tz: query.timeZone,
        shapes: query.shapes,
        step: query.step,
        compare: query.compare,
    };
    if (query.project !== null) params.project = String(query.project);
    if (query.annotator !== null) params.annotator = String(query.annotator);
    if (query.ids.length) params.ids = query.ids.join(',');
    try {
        const answer = await request('trends', params);
        const data = answer.body;
        reportRefusal(answer);
        const readable = succeeded(answer) && !!data && Array.isArray(data.buckets) && Array.isArray(data.lines) &&
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

// A row's working time split by operation: each operation's figures and Other (working time less them, never
// below zero)
export type RowOperations = Record<'creation' | 'alignment' | 'class_change' | 'deletion', ListFigures> & {
    other: { time_ms: number };
};

// One annotator or project of a full view
export interface ListRow {
    id: number; // project 0 = No project
    user_name: string | null; // annotators only
    working_time_ms: number;
    // of all rows' working time; null when there is none
    share: number | null;
    operations: RowOperations;
    methods: Record<CreationMethodName, ListFigures>;
    // objects no person drew: detector boxes, and for a project also what technical accounts saved
    model: number;
}

export interface HotkeyListRow {
    action: string;
    actions: number;
    share: number; // of all hotkey actions
}

// In a period not wholly processed (`processed: false`) a list keeps its envelope (period, kind, legacy flags)
// and its figures (`total`, `rows`, `hotkey_actions`) are null.
export interface RowsList {
    by: 'annotators' | 'projects';
    period?: Period;
    // false: the period is not wholly processed, so it carries no figures
    processed?: boolean;
    legacy: boolean;
    // as OperationsFigures: the cutover falls inside the period, and when it is
    partly_legacy?: boolean;
    cutover?: string | null;
    shapes: 'bounding_boxes' | 'all';
    total: { count: number; working_time_ms: number } | null;
    rows: ListRow[] | null;
}

export interface HotkeysList {
    by: 'hotkeys';
    period?: Period;
    processed?: boolean;
    hotkey_actions: number | null;
    rows: HotkeyListRow[] | null;
}

export type FullList = RowsList | HotkeysList;

// Every row of one chart for a full view, or null when the list cannot be read (the full view says so).
export async function loadList(
    query: OverviewQuery & { by: ListKind }, request: RequestService = requestService,
): Promise<FullList | null> {
    try {
        const answer = await request('list', { ...serviceParams(query), by: query.by });
        const data = answer.body;
        reportRefusal(answer);
        const readable = succeeded(answer) && !!data && data.by === query.by &&
            (Array.isArray(data.rows) || data.processed === false);
        return readable ? data as FullList : null;
    } catch {
        return null;
    }
}

// --- filter options: the projects or annotators of the Project and Annotator selectors ---------------------------

export type FilterKind = 'projects' | 'annotators';

// One option of a selector: a project (0 = No project, named by the page) or an annotator with their name
export interface FilterOption {
    id: number;
    user_name: string | null;
}

// The options, or why there are none: the period is not processed yet (`withheld`), or the list failed.
export type FilterOptions =
    | { kind: 'ready'; options: FilterOption[] }
    | { kind: 'withheld' }
    | { kind: 'failed' };

// Everyone of `kind` with job work in the period, asked through the full view list (GET list) without the
// project, annotator and shapes parameters, so that one selector's options do not depend on the other filter.
export async function loadFilterOptions(
    query: OverviewQuery & { by: FilterKind }, request: RequestService = requestService,
): Promise<FilterOptions> {
    const list = await loadList({
        organization: query.organization,
        timeZone: query.timeZone,
        period: query.period,
        month: query.month,
        by: query.by,
    }, request) as RowsList | null;
    if (!list) return { kind: 'failed' };
    if (!list.rows) return { kind: 'withheld' };
    return { kind: 'ready', options: list.rows.map((row) => ({ id: row.id, user_name: row.user_name })) };
}

// --- project names (GET project-names): names of any projects, whatever their organization -------------------

// Ids asked per request; the API refuses more (400).
export const PROJECT_NAMES_PER_REQUEST = 500;

// The names of the existing projects among `ids` (at most PROJECT_NAMES_PER_REQUEST positive ids); an unknown
// id is simply absent. Throws when the answer is not a success. CVAT's own projects API names, with no
// organization selected, only personal-workspace projects, so the fork's API names them for the page.
export async function requestProjectNames(
    ids: number[], request: RequestService = requestService,
): Promise<ProjectNames> {
    const answer = await request('project-names', { ids: ids.join(',') });
    const names = answer.body?.names;
    if (!succeeded(answer) || !names || typeof names !== 'object') {
        throw new Error(`project names were not returned (${answer.status})`);
    }
    const result: ProjectNames = {};
    for (const [id, name] of Object.entries(names)) {
        if (typeof name === 'string') result[Number(id)] = name;
    }
    return result;
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

// In a period not wholly processed (`processed: false`) the table keeps its envelope (kind, page size, legacy
// flags) and `page`, `total`, `rows` and `project_ids` are null.
export interface Details {
    by: DetailsKind;
    page: number | null; // 1-based, the page actually shown
    page_size: number;
    total: number | null; // rows matching the search
    legacy: boolean;
    partly_legacy?: boolean; // as OperationsFigures
    cutover?: string | null;
    shapes: 'bounding_boxes' | 'all';
    processed?: boolean;
    technical_accounts?: number;
    rows: DetailsRow[] | null;
    // projects only: every project in the table before the search, for finding projects by name
    project_ids?: number[] | null;
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
export async function loadDetails(
    query: DetailsQuery, request: RequestService = requestService,
): Promise<Details | null> {
    const params: Record<string, string> = { ...serviceParams(query), by: query.by, page: String(query.page) };
    if (query.search) params.search = query.search;
    if (query.ids) params.ids = query.ids.join(',');
    try {
        const answer = await request('details', params);
        const data = answer.body;
        reportRefusal(answer);
        const readable = succeeded(answer) && !!data &&
            ((Array.isArray(data.rows) && typeof data.total === 'number') || data.processed === false);
        return readable ? data as Details : null;
    } catch {
        return null;
    }
}

// --- Team Analytics settings (GET and PUT settings, GET settings/users): the Technical accounts list -----------

// One technical account: its user, by id, with the live user's name, or the last known name of a user that no
// longer exists (`deleted`).
export interface TechnicalAccount {
    user_id: number;
    user_name: string;
    deleted: boolean;
}

export interface TeamAnalyticsSettings {
    technical_accounts: TechnicalAccount[];
}

// A user the settings screen offers to add: any user of the instance.
export interface SettingsUser {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
}

// Reads (GET) or replaces (PUT, with `body`) the settings. Answers every HTTP answer, a refusal or failure
// too, with the text cvat-core made of an error body; throws only when there is no answer at all. Tests
// replace it.
export type RequestSettings = (method: 'GET' | 'PUT', body?: object) => Promise<ServiceAnswer>;

export const requestSettings: RequestSettings = async (method, body) => {
    const core = getCore();
    try {
        const response = await core.server.request(`${core.config.backendAPI}/${SERVICE_PATH}/settings`, {
            method,
            ...(body === undefined ? {} : { data: body }),
        }) as { status: number; data: unknown };
        return { status: response.status, body: response.data ?? null };
    } catch (error) {
        if (error instanceof ServerError && error.code >= 100) {
            return { status: error.code, body: null, message: error.message };
        }
        throw error;
    }
};

function readableSettings(body: any): body is TeamAnalyticsSettings {
    return !!body && Array.isArray(body.technical_accounts) && body.technical_accounts.every(
        (account: TechnicalAccount) => typeof account?.user_id === 'number' && typeof account.user_name === 'string',
    );
}

// The settings, or null when they cannot be read (the settings screen says so). A refusal takes the page to it.
export async function loadSettings(request: RequestSettings = requestSettings): Promise<TeamAnalyticsSettings | null> {
    try {
        const answer = await request('GET');
        reportRefusal(answer);
        return succeeded(answer) && readableSettings(answer.body) ? answer.body : null;
    } catch {
        return null;
    }
}

// Without an answer, or with a server failure, the list may or may not have been saved (the server answers 503
// when the list was saved but older answers could not be retired)
export const SAVE_UNFINISHED = 'The save did not finish, so the list may not have changed. Open the settings again ' +
    'to see the saved list.';

export type SaveResult = { kind: 'saved'; settings: TeamAnalyticsSettings } | { kind: 'failed'; error: string };

// Replaces the Technical accounts list with `ids` (the whole list). A failure is said in a sentence the screen
// shows: a refused list (400) in the server's words.
export async function saveSettings(
    ids: number[], request: RequestSettings = requestSettings,
): Promise<SaveResult> {
    let answer: ServiceAnswer;
    try {
        answer = await request('PUT', { technical_accounts: ids });
    } catch {
        return { kind: 'failed', error: SAVE_UNFINISHED };
    }
    if (succeeded(answer) && readableSettings(answer.body)) return { kind: 'saved', settings: answer.body };
    if (answer.status === 400) {
        return { kind: 'failed', error: answer.message || answer.body?.detail || 'The list was refused.' };
    }
    if (answer.status === 401) return { kind: 'failed', error: 'Your session has ended. Sign in again to save.' };
    if (answer.status === 403) {
        return { kind: 'failed', error: 'Only administrators can change Team Analytics settings.' };
    }
    return { kind: 'failed', error: SAVE_UNFINISHED };
}

// Users of the whole instance whose user name, first or last name contains `search` (at most 20, by user name),
// or null when the search failed.
export async function searchUsers(
    search: string, request: RequestService = requestService,
): Promise<SettingsUser[] | null> {
    try {
        const answer = await request('settings/users', { search });
        reportRefusal(answer);
        const users = answer.body?.users;
        return succeeded(answer) && Array.isArray(users) ? users as SettingsUser[] : null;
    } catch {
        return null;
    }
}
