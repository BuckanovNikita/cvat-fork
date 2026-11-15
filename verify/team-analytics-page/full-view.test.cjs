// Full view: any chart opened alone on the page with every row (search, sorting, whole names), kept in the
// page address, closed with "Back to overview" or the browser's Back button, with the period, the shape
// switch and the filters still working. Lists come from the service's `list` response.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const HOUR = 3600000;
const LONG_NAME = 'annotator.with.a.very.long.name.from.the.northern.district.second.shift';

function opsRow(operation, objects, timeMs) {
    return {
        operation, objects, timed_objects: objects, time_ms: timeMs,
        average_ms: objects ? timeMs / objects : null, share: 0.2, hotkey_objects: 0, mouse_objects: objects,
    };
}

const OVERVIEW = {
    period: {
        name: 'week', first_day: '2026-11-07', last_day: '2026-11-13', month: null, to_date: false, unit: 'day',
    },
    by_annotator: {
        rows: [
            { user_id: 11, user_name: 'alice', working_time_ms: 9 * HOUR },
            { user_id: 12, user_name: 'bob', working_time_ms: 8 * HOUR },
        ],
        rest: { count: 10, working_time_ms: 20 * HOUR },
    },
    by_project: { rows: [{ project_id: 1, working_time_ms: 10 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    headline: { annotators: 12, projects: 1 },
    filters: { project: null, annotator: null },
    time_series: {
        unit: 'day',
        buckets: ['07', '08', '09', '10', '11', '12', '13'].map((day, index) => ({
            start: `2026-11-${day}`, working_time_ms: (index + 1) * HOUR,
        })),
    },
    operations: {
        legacy: false,
        shapes: 'bounding_boxes',
        working_time_ms: 37 * HOUR,
        active_time_ms: 37 * HOUR,
        rows: [opsRow('creation', 100, 400000), opsRow('alignment', 10, 50000), opsRow('class_change', 2, 4000),
            opsRow('deletion', 3, 3000), opsRow('other', 0, 37 * HOUR - 457000)],
    },
    creation_methods: {
        shapes: 'bounding_boxes',
        rows: [
            { method: 'drawn', objects: 90, timed_objects: 90, time_ms: 360000, average_ms: 4000, share: 0.8 },
            { method: 'pasted', objects: 10, timed_objects: 10, time_ms: 40000, average_ms: 4000, share: 0.1 },
            { method: 'propagated', objects: 0, timed_objects: 0, time_ms: 0, average_ms: null, share: 0 },
        ],
        total: { objects: 100, timed_objects: 100, time_ms: 400000, average_ms: 4000 },
        model: { objects: 12, share: 0.1 },
        technical_accounts: 0,
    },
    input: {
        hotkey_actions: 300,
        mouse_actions: 100,
        canvas_clicks: 50,
        hotkey_share: 0.75,
        top_hotkeys: [{ action: 'NEXT_FRAME', actions: 200 }],
        rest: { count: 2, actions: 100 },
    },
    processed: true,
};

function figures(objects, timeMs) {
    return {
        objects, timed_objects: objects, time_ms: timeMs, average_ms: objects ? timeMs / objects : null,
    };
}

// one list row: working time split as creation 1/4, other the rest
function listRow(id, name, hours, extra = {}) {
    return {
        id,
        user_name: name,
        working_time_ms: hours * HOUR,
        share: hours / 37,
        operations: {
            creation: figures(10 * hours, hours * HOUR / 4),
            alignment: figures(hours, 0),
            class_change: figures(0, 0),
            deletion: figures(1, 2000),
            other: { time_ms: hours * HOUR * 0.75 - 2000 },
        },
        methods: {
            drawn: figures(8 * hours, hours * HOUR / 5),
            pasted: figures(2 * hours, hours * HOUR / 20),
            propagated: figures(0, 0),
        },
        model: hours,
        ...extra,
    };
}

const ANNOTATORS = [
    listRow(11, 'alice', 9), listRow(12, 'bob', 8),
    ...Array.from({ length: 10 }, (_, index) => listRow(20 + index, `${index === 9 ? LONG_NAME : `user${index}`}`, 2)),
];
ANNOTATORS[ANNOTATORS.length - 1].working_time_ms = 2 * HOUR;

function listAnswer(url) {
    const params = new URL(url, 'http://localhost').searchParams;
    const base = { period: OVERVIEW.period, processed: true, by: params.get('by') };
    if (params.get('by') === 'hotkeys') {
        return {
            body: {
                ...base,
                hotkey_actions: 300,
                rows: [
                    { action: 'NEXT_FRAME', actions: 200, share: 2 / 3 },
                    { action: 'SAVE_JOB', actions: 60, share: 0.2 },
                    { action: 'UNKNOWN_ACTION', actions: 40, share: 40 / 300 },
                ],
            },
        };
    }
    const rows = params.get('by') === 'projects' ?
        [listRow(1, null, 10), listRow(0, null, 3), listRow(7, null, 1)] : ANNOTATORS;
    return {
        body: {
            ...base,
            legacy: false,
            shapes: params.get('shapes') === 'all' ? 'all' : 'bounding_boxes',
            total: { count: rows.length, working_time_ms: 37 * HOUR },
            rows,
        },
    };
}

const WEEKS = ['2026-08-24', '2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05',
    '2026-10-12', '2026-10-19', '2026-10-26', '2026-11-02', '2026-11-09'];

function trendsAnswer(url = '') {
    const ids = (new URL(url, 'http://localhost').searchParams.get('ids') ?? '').split(',').filter(Boolean).map(Number);
    const point = (index) => ({
        working_time_ms: (index + 1) * HOUR, legacy: false, boxes: 10 * (index + 1), timed_boxes: 10 * (index + 1),
        box_time_ms: 40000 * (index + 1), average_ms: 4000, hotkey_recorded: true, hotkey_actions: 3,
        mouse_actions: 1, hotkey_share: 0.75,
    });
    return {
        body: {
            step: 'week', tz: 'UTC', shapes: 'bounding_boxes', compare: 'annotators',
            buckets: WEEKS.map((start) => ({ start, processed: true })),
            lines: (ids.length ? ids : [null]).map((id) => ({
                id, user_name: id === 11 ? 'alice' : null, points: WEEKS.map((_, index) => point(index)),
            })),
            candidates: [{ id: 11, user_name: 'alice', working_time_ms: HOUR }],
        },
    };
}

function answer(url) {
    if (url.includes('/list?')) return listAnswer(url);
    if (url.includes('/trends?')) return trendsAnswer(url);
    if (url.includes('/status?')) return { body: {} };
    return { body: OVERVIEW };
}

const KEYMAP = {
    keyMap: { NEXT_FRAME: { name: 'Next frame' }, SAVE_JOB: { name: 'Save the job' } },
    normalizedKeyMap: { NEXT_FRAME: '[f]', SAVE_JOB: '[Ctrl+s]' },
};

const { createMemoryHistory } = dependency('history');

function openPage({ search = '', respond = answer, names = async () => ({ 1: 'Street scenes' }) } = {}) {
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const { request, requests } = suppliedService(respond);
    const lookups = [];
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': {
            useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } }, shortcuts: KEYMAP }),
        },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async (ids) => { lookups.push(ids); return names(ids); } },
    }).default;
    return {
        history, requests, lookups, Page,
    };
}

// Mounts the page, runs `check` on it and always unmounts (the status timer would keep node alive).
async function opened(Page, check) {
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        await check(view);
    } finally {
        await view.unmount();
    }
}

async function click(element) {
    assert.ok(element, 'the control is on the page');
    await act(async () => { element.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
}

async function type(input, value) {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await act(async () => {
        setter.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
}

const search = (history) => new URLSearchParams(history.location.search);
const params = (request) => new URL(request.url, 'http://localhost').searchParams;
const listRequests = (requests) => requests.filter((request) => request.url.includes('/list?')).map(params);

function button(root, label) {
    return [...root.querySelectorAll('button')].find((element) => element.textContent.trim() === label);
}

function fullViewButton(container, cardClass) {
    const card = container.querySelector(`.${cardClass}`);
    assert.ok(card, `${cardClass} is on the overview`);
    return card.querySelector('.cvat-team-analytics-full-view-button');
}

function fullView(container) {
    return container.querySelector('.cvat-team-analytics-full-view');
}

function listRows(container) {
    return [...container.querySelectorAll('.cvat-team-analytics-full-list-row')].map((row) => [
        row.querySelector('.cvat-team-analytics-full-rank').textContent,
        row.querySelector('.cvat-team-analytics-full-name').textContent,
        row.querySelector('.cvat-team-analytics-full-value').textContent,
        row.querySelector('.cvat-team-analytics-full-share').textContent,
    ]);
}

// --- every chart has a Full view button ----------------------------------------------------------

const View = loadPage('team-analytics-view.tsx').default;
const WEEK = {
    period: 'week', month: null, project: null, annotator: null, shapes: 'bounding_boxes',
};

test('every chart on the overview has a Full view button', () => {
    const html = render(View, {
        organization: 'team-org', state: { kind: 'ready', overview: OVERVIEW }, address: WEEK, onAddressChange() {},
    });
    const cards = [...html.matchAll(/<section class="cvat-team-analytics-card ([^" ]+)[^"]*"[^>]*>(.*?)<\/section>/g)]
        .filter((match) => match[2].includes('cvat-team-analytics-full-view-button'))
        .map((match) => match[1]);
    assert.deepEqual(cards, [
        'cvat-team-analytics-time-chart', 'cvat-team-analytics-split', 'cvat-team-analytics-operations',
        'cvat-team-analytics-creation-methods', 'cvat-team-analytics-working-time-by-project',
        'cvat-team-analytics-working-time-by-annotator', 'cvat-team-analytics-keyboard',
    ]);
});

test('each of the four trend charts has a Full view button', () => {
    const Card = loadPage('cards/trends-card.tsx').default;
    const html = render(Card, {
        trends: trendsAnswer().body, step: 'week', kind: 'annotators', compared: [], query: '',
        scopeLabel: 'All annotators · All projects', onOpenFull() {},
    });
    const charts = [...html.matchAll(/<figure[^>]*cvat-team-analytics-trend-chart[^>]*>(.*?)<\/figure>/g)];
    assert.equal(charts.length, 4);
    for (const chart of charts) assert.match(chart[1], /cvat-team-analytics-full-view-button.*?Full view<\/button>/);
});

test('a card on the overview keeps its top rows; its show all control names every row', () => {
    const html = render(View, {
        organization: 'team-org', state: { kind: 'ready', overview: OVERVIEW }, address: WEEK, onAddressChange() {},
    });
    const annotators = html.match(/cvat-team-analytics-working-time-by-annotator[^>]*>(.*?)<\/section>/)[1];
    assert.equal([...annotators.matchAll(/cvat-team-analytics-annotator-row/g)].length, 2);
    assert.match(text(annotators), /10 more, not shown 20\.0 h Show all 12 in full view$/);
    const keyboard = html.match(/cvat-team-analytics-keyboard"[^>]*>(.*?)<\/section>/)[1];
    assert.match(text(keyboard), /Show all 3 in full view$/);
});

// --- opening, closing and the address ------------------------------------------------------------

test('a full view replaces the overview, keeps the header and filters, and is part of the address', async () => {
    const { history, requests, Page } = openPage();
    await opened(Page, async (view) => {
        await click(fullViewButton(view.container, 'cvat-team-analytics-working-time-by-annotator'));
        await view.settle();

        assert.equal(search(history).get('view'), 'annotators');
        assert.equal(view.container.querySelector('.cvat-team-analytics-cards') === null, true, 'the overview is replaced');
        assert.equal(view.container.querySelector('.cvat-team-analytics-details') === null, true,
            'the details table stays on the overview');
        assert.ok(view.container.querySelector('.cvat-team-analytics-header'));
        assert.ok(view.container.querySelector('.cvat-team-analytics-filters'));
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'Working time by annotator');
        assert.equal(listRequests(requests).at(-1).get('by'), 'annotators');

        await click(button(view.container, 'Back to overview'));
        await view.settle();
        assert.equal(search(history).get('view'), null);
        assert.ok(view.container.querySelector('.cvat-team-analytics-cards'));

        await act(async () => { history.goBack(); });
        await view.settle();
        assert.equal(search(history).get('view'), 'annotators', 'Back returns to the full view');
        assert.ok(fullView(view.container));
        await act(async () => { history.goBack(); });
        await view.settle();
        assert.equal(fullView(view.container), null, 'and once more to the overview');
        assert.ok(view.container.querySelector('.cvat-team-analytics-cards'));
    });
});

test('a shared address opens its full view; an unknown one shows the overview', async () => {
    const shared = openPage({ search: '?period=week&view=hotkeys' });
    await opened(shared.Page, async (view) => {
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'Hotkey usage');
    });
    const unknown = openPage({ search: '?view=everything' });
    await opened(unknown.Page, async (view) => {
        assert.equal(fullView(view.container), null);
        assert.ok(view.container.querySelector('.cvat-team-analytics-cards'));
        assert.equal(listRequests(unknown.requests).length, 0);
    });
});

test('the show all control of a chart opens its full view', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container.querySelector('.cvat-team-analytics-working-time-by-annotator'),
            'Show all 12 in full view'));
        await view.settle();
        assert.equal(search(history).get('view'), 'annotators');
        assert.equal(listRows(view.container).length, 12);
    });
});

// --- lists ---------------------------------------------------------------------------------------

test('by annotator: every row with its rank, whole name, bar, value and share; search and sorting', async () => {
    const { Page } = openPage({ search: '?view=annotators' });
    await opened(Page, async (view) => {
        const rows = listRows(view.container);
        assert.equal(rows.length, 12);
        assert.deepEqual(rows[0], ['1', 'alice', '9.0 h', '24%']);
        assert.deepEqual(rows[11], ['12', LONG_NAME, '2.0 h', '5%'], 'the whole name, never shortened');
        const firstRow = view.container.querySelector('.cvat-team-analytics-full-list-row');
        assert.equal(firstRow.querySelectorAll('.cvat-team-analytics-full-bar-part').length, 5,
            'the bar is split by operation and Other');
        assert.match(text(fullView(view.container).querySelector('.cvat-team-analytics-full-summary').innerHTML),
            /12 annotators · 37\.0 h in total/);

        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), 'USER');
        assert.deepEqual(listRows(view.container).map((row) => row[0]), ['3', '4', '5', '6', '7', '8', '9', '10', '11'],
            'a found row keeps its rank');
        await click(button(view.container, 'By name'));
        assert.deepEqual(listRows(view.container).slice(0, 2).map((row) => row[1]), ['user0', 'user1']);
        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), 'zzz');
        assert.equal(listRows(view.container).length, 0);
        assert.match(fullView(view.container).textContent, /No match for this search/);
        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), '');
        await click(button(view.container, 'By value'));
        assert.deepEqual(listRows(view.container).slice(0, 2).map((row) => row[1]), ['alice', 'bob']);
    });
});

test('by project: names from the names lookup, No project, an unknown project by its identifier', async () => {
    const { lookups, Page } = openPage({ search: '?view=projects' });
    await opened(Page, async (view) => {
        assert.deepEqual(listRows(view.container).map((row) => row[1]), ['Street scenes', 'No project', 'Project #7']);
        assert.ok(lookups.some((ids) => ids.includes(7)), 'every listed project is asked of CVAT');
        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), 'street');
        assert.deepEqual(listRows(view.container).map((row) => row[1]), ['Street scenes']);
    });
});

test('the legend sits at the top of a full view, above the rows', async () => {
    const { Page } = openPage({ search: '?view=split' });
    await opened(Page, async (view) => {
        const full = fullView(view.container);
        const legend = full.querySelector('.cvat-team-analytics-full-legend');
        assert.ok(legend);
        assert.match(legend.textContent, /Creation.*Alignment.*Class change.*Deletion.*Other/);
        const firstRow = full.querySelector('.cvat-team-analytics-full-list-row');
        // eslint-disable-next-line no-bitwise
        assert.ok(legend.compareDocumentPosition(firstRow) & window.Node.DOCUMENT_POSITION_FOLLOWING);
    });
});

test('where working time goes: the same list with a switch between annotators and projects', async () => {
    const { history, requests, Page } = openPage({ search: '?view=split' });
    await opened(Page, async (view) => {
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'Where working time goes, by annotator');
        assert.equal(listRows(view.container).length, 12);
        await click(button(view.container.querySelector('[aria-label="Rows"]'), 'Projects'));
        await view.settle();
        assert.equal(search(history).get('rows'), 'projects');
        assert.equal(listRequests(requests).at(-1).get('by'), 'projects');
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'Where working time goes, by project');
        assert.deepEqual(listRows(view.container).map((row) => row[1]), ['Street scenes', 'No project', 'Project #7']);
    });
});

test('clicking a row in a list sets the page filter, as on the overview', async () => {
    const { history, requests, Page } = openPage({ search: '?view=annotators' });
    await opened(Page, async (view) => {
        const bob = [...view.container.querySelectorAll('.cvat-team-analytics-full-list-row')][1];
        await click(bob);
        await view.settle();
        assert.equal(search(history).get('annotator'), '12');
        assert.equal(search(history).get('view'), 'annotators', 'the full view stays open');
        assert.equal(params(requests.filter((r) => r.url.includes('/overview?')).at(-1)).get('annotator'), '12');
        const marked = [...view.container.querySelectorAll('.cvat-team-analytics-full-list-row')][1];
        assert.equal(marked.getAttribute('aria-pressed'), 'true');
        assert.match(view.container.querySelector('.cvat-team-analytics-filter-annotator').textContent, /bob/);
    });
});

test('the period, the shape switch and the filters still work inside a full view', async () => {
    const { history, requests, Page } = openPage({ search: '?view=split&rows=projects' });
    await opened(Page, async (view) => {
        await click(button(view.container.querySelector('.cvat-team-analytics-filters'), 'Two weeks'));
        await view.settle();
        assert.equal(search(history).get('view'), 'split');
        assert.equal(listRequests(requests).at(-1).get('period'), 'two_weeks');
        await click(button(view.container.querySelector('.cvat-team-analytics-filters'), 'All shapes'));
        await view.settle();
        assert.equal(listRequests(requests).at(-1).get('shapes'), 'all');
        await act(async () => { history.push('/team-analytics?view=split&rows=projects&period=two_weeks&annotator=11&org=team-org'); });
        await view.settle();
        const last = listRequests(requests).at(-1);
        assert.deepEqual([last.get('by'), last.get('annotator'), last.get('org')], ['projects', '11', null]);
        assert.ok(fullView(view.container));
    });
});

test('hotkeys: every hotkey labelled from the viewer keymap with its keys, count and share', async () => {
    const { requests, Page } = openPage({ search: '?view=hotkeys' });
    await opened(Page, async (view) => {
        assert.equal(listRequests(requests).at(-1).get('by'), 'hotkeys');
        assert.deepEqual(listRows(view.container), [
            ['1', 'Next frame', '200', '67%'], ['2', 'Save the job', '60', '20%'], ['3', 'UNKNOWN_ACTION', '40', '13%'],
        ]);
        assert.deepEqual([...view.container.querySelectorAll('.cvat-team-analytics-full-extra')]
            .map((cell) => cell.textContent), ['f', 'Ctrl+s', '—']);
        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), 'ctrl');
        assert.deepEqual(listRows(view.container).map((row) => row[1]), ['Save the job'], 'found by key too');
    });
});

// --- tables --------------------------------------------------------------------------------------

function tableRows(container) {
    return [...container.querySelectorAll('.cvat-team-analytics-full-table tbody tr')]
        .map((row) => [...row.children].map((cell) => cell.textContent));
}

function tableHeader(container) {
    return [...container.querySelectorAll('.cvat-team-analytics-full-table thead th')].map((cell) => cell.textContent);
}

test('operations: a table by annotator or by project with a switch between the two', async () => {
    const { history, Page } = openPage({ search: '?view=operations' });
    await opened(Page, async (view) => {
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'Bounding box operations, by annotator');
        assert.deepEqual(tableHeader(view.container), ['Annotator', 'Created', 'Avg create', 'Aligned', 'Avg align',
            'Class changes', 'Avg change', 'Deleted', 'Avg delete']);
        assert.equal(tableRows(view.container).length, 12);
        assert.deepEqual(tableRows(view.container)[0], ['alice', '90', '90 s', '9', '0.0 s', '0', '—', '1', '2.0 s']);
        await click(button(view.container.querySelector('[aria-label="Rows"]'), 'Projects'));
        await view.settle();
        assert.equal(search(history).get('rows'), 'projects');
        assert.equal(tableHeader(view.container)[0], 'Project');
        assert.deepEqual(tableRows(view.container).map((row) => row[0]), ['Street scenes', 'No project', 'Project #7']);
        await type(view.container.querySelector('.cvat-team-analytics-full-view input[type="search"]'), 'project');
        assert.deepEqual(tableRows(view.container).map((row) => row[0]), ['No project', 'Project #7']);
    });
});

test('creation methods: a table with each method, Model and all annotator methods', async () => {
    const { Page } = openPage({ search: '?view=methods' });
    await opened(Page, async (view) => {
        assert.equal(fullView(view.container).querySelector('h2').textContent, 'How boxes are created, by annotator');
        assert.deepEqual(tableHeader(view.container), ['Annotator', 'Drawn', 'Avg drawn', 'Pasted', 'Avg pasted',
            'Propagated', 'Avg propagated', 'Model', 'All annotator methods', 'Avg all']);
        assert.deepEqual(tableRows(view.container)[1], ['bob', '64', '90 s', '16', '90 s', '0', '—', '8', '80', '90 s']);
        await click(button(view.container, 'By name'));
        assert.deepEqual(tableRows(view.container).slice(0, 3).map((row) => row[0]), ['alice', LONG_NAME, 'bob']);
    });
});

// --- time and trends -----------------------------------------------------------------------------

test('working time over the period: a large chart and every value listed', async () => {
    const { requests, Page } = openPage();
    await opened(Page, async (view) => {
        await click(fullViewButton(view.container, 'cvat-team-analytics-time-chart'));
        await view.settle();
        const full = fullView(view.container);
        assert.equal(full.querySelector('h2').textContent, 'Working time by day');
        assert.ok(full.querySelector('.cvat-team-analytics-time-chart-large'));
        assert.deepEqual([...full.querySelectorAll('.cvat-team-analytics-full-values li')].map((item) => item.textContent),
            ['Nov 71.0 h', 'Nov 82.0 h', 'Nov 93.0 h', 'Nov 104.0 h', 'Nov 115.0 h', 'Nov 126.0 h', 'Nov 137.0 h']);
        assert.equal(listRequests(requests).length, 0, 'every value is in the overview already');
    });
});

test('a trend: a large chart, a legend with whole names and latest values on top, all twelve points', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        const charts = [...view.container.querySelectorAll('.cvat-team-analytics-trend-chart')];
        assert.equal(charts.length, 4);
        await click(charts[1].querySelector('.cvat-team-analytics-full-view-button'));
        await view.settle();
        assert.equal(search(history).get('view'), 'trend-boxes');
        const full = fullView(view.container);
        assert.equal(full.querySelector('h2').textContent, 'Boxes created');
        const chart = full.querySelector('.cvat-team-analytics-trend-chart');
        assert.ok(chart.classList.contains('cvat-team-analytics-trend-chart-large'));
        const legend = chart.querySelector('.cvat-team-analytics-trend-legend');
        assert.equal(legend.textContent, 'All annotators · All projects120');
        // eslint-disable-next-line no-bitwise
        assert.ok(legend.compareDocumentPosition(chart.querySelector('svg')) & window.Node.DOCUMENT_POSITION_FOLLOWING,
            'the legend is above the chart');
        assert.equal(chart.querySelector('details') === null, true, 'the values are not folded away');
        assert.equal(chart.querySelectorAll('tbody tr').length, 12);
        await click(button(view.container, 'Back to overview'));
        await view.settle();
        assert.equal(view.container.querySelectorAll('.cvat-team-analytics-trend-chart').length, 4);
    });
});

// A list of a period not wholly processed, as the service sends it: the envelope, and every figure null.
function noFiguresList(url) {
    const by = new URL(url, 'http://localhost').searchParams.get('by');
    const envelope = { period: OVERVIEW.period, processed: false, by };
    if (by === 'hotkeys') return { body: { ...envelope, hotkey_actions: null, rows: null } };
    return {
        body: {
            ...envelope, legacy: false, partly_legacy: false, cutover: null, shapes: 'bounding_boxes', total: null, rows: null,
        },
    };
}

for (const search of ['?view=annotators', '?view=projects', '?view=split&rows=projects', '?view=hotkeys']) {
    test(`a full view of a period not wholly processed shows no partial figures (${search})`, async () => {
        const { Page, lookups } = openPage({
            search,
            respond: (url) => (url.includes('/list?') ? noFiguresList(url) : answer(url)),
        });
        await opened(Page, async (view) => {
            assert.equal(listRows(view.container).length, 0);
            assert.ok(view.container.querySelector('.cvat-team-analytics-not-processed'));
            assert.doesNotMatch(view.container.textContent, /could not be loaded/);
            assert.deepEqual(lookups.filter((ids) => ids.includes(7)), [], 'no list row asks for a name');
        });
    });
}

test('a trend full view keeps the comparison chosen on the overview', async () => {
    const { requests, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container.querySelector('.cvat-team-analytics-trends'), '+ alice'));
        await view.settle();
        const charts = [...view.container.querySelectorAll('.cvat-team-analytics-trend-chart')];
        await click(charts[0].querySelector('.cvat-team-analytics-full-view-button'));
        await view.settle();
        const legend = fullView(view.container).querySelector('.cvat-team-analytics-trend-legend');
        assert.match(legend.textContent, /^alice/);
        const last = requests.filter((request) => request.url.includes('/trends?')).map(params).at(-1);
        assert.equal(last.get('ids'), '11');
    });
});

test('a list that cannot be updated keeps the previous rows dimmed and says so', async () => {
    let lists = 0;
    const { history, Page } = openPage({
        search: '?view=annotators',
        respond: (url) => {
            if (url.includes('/list?')) {
                lists += 1;
                return lists === 1 ? listAnswer(url) : { status: 500, body: { error: 'internal' } };
            }
            return answer(url);
        },
    });
    await opened(Page, async (view) => {
        assert.equal(listRows(view.container).length, 12);
        await act(async () => { history.push('/team-analytics?view=annotators&project=1&org=team-org'); });
        await view.settle();
        assert.ok(fullView(view.container).classList.contains('cvat-team-analytics-pending'));
        assert.match(fullView(view.container).querySelector('.cvat-team-analytics-full-failed').textContent,
            /could not be updated/);
    });
});

test('a project with no working time is left out of the working time list but stays in the tables', async () => {
    const respond = (url) => {
        if (!url.includes('/list?') || !url.includes('by=projects')) return answer(url);
        const body = listAnswer(url).body;
        const idle = { ...listRow(9, null, 0), model: 5 };
        return { body: { ...body, total: { ...body.total, count: 4 }, rows: [...body.rows, idle] } };
    };
    const lists = openPage({ search: '?view=projects', respond });
    await opened(lists.Page, async (view) => {
        assert.deepEqual(listRows(view.container).map((row) => row[1]), ['Street scenes', 'No project', 'Project #7']);
        assert.match(fullView(view.container).querySelector('.cvat-team-analytics-full-summary').textContent,
            /^3 projects/);
    });
    const tables = openPage({ search: '?view=methods&rows=projects', respond });
    await opened(tables.Page, async (view) => {
        assert.equal(tableRows(view.container).at(-1)[0], 'Project #9');
        assert.equal(tableRows(view.container).at(-1)[7], '5');
    });
});
