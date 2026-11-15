// Details table: every figure for every annotator, or every project, ten rows a page, searchable, from the
// `details` response the service sends.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const HOUR = 3600000;

function row(id, overrides = {}) {
    return {
        id,
        user_name: `user${id}`,
        projects: 2,
        sessions: 3,
        working_time_ms: 2.5 * HOUR,
        drawn: 1200,
        pasted: 3,
        propagated: 2,
        model: 4,
        saved_boxes: 9,
        alignments: 1,
        class_changes: 2,
        deletions: 1,
        average_create_ms: 5000,
        hotkey_share: 0.75,
        ...overrides,
    };
}

function details(overrides = {}) {
    return {
        by: 'annotators',
        page: 1,
        page_size: 10,
        total: 2,
        legacy: false,
        shapes: 'bounding_boxes',
        processed: true,
        technical_accounts: 1,
        rows: [row(11, { user_name: 'alice' }), row(12, { user_name: 'bob', hotkey_share: null, average_create_ms: null })],
        ...overrides,
    };
}

const Card = loadPage('cards/details-table-card.tsx').default;

function card(props = {}) {
    return render(Card, {
        details: details(), by: 'annotators', search: '', selected: null, ...props,
    });
}

function cells(html) {
    return [...html.matchAll(/<tr[^>]*>(.*?)<\/tr>/g)].map((m) => [...m[1].matchAll(/<t[hd][^>]*>(.*?)<\/t[hd]>/g)]
        .map((cell) => text(cell[1])));
}

test('annotators: every figure in one row each, under the columns of the table', () => {
    const [header, alice, bob] = cells(card());
    assert.deepEqual(header, ['Annotator', 'Projects', 'Sessions', 'Working time', 'Drawn', 'Pasted', 'Propagated',
        'Model', 'Alignments', 'Class changes', 'Deletions', 'Avg time to create', 'Hotkey share']);
    assert.deepEqual(alice, ['alice', '2', '3', '2.5 h', '1,200', '3', '2', '4', '1', '2', '1', '5.0 s', '75%']);
    assert.deepEqual(bob.slice(-2), ['—', '—']);
    assert.match(text(card()), /Sorted by working time/);
});

test('projects: named as CVAT names them, with the annotators who worked in each', () => {
    const shown = details({
        by: 'projects',
        rows: [row(3, { user_name: null, annotators: 4 }), row(0, { user_name: null, annotators: 1 }),
            row(8, { user_name: null, annotators: 2 })],
        project_ids: [0, 3, 8],
        total: 3,
    });
    const [header, ...rows] = cells(card({ details: shown, by: 'projects', projectNames: { 3: 'Cats' } }));
    assert.deepEqual(header.slice(0, 2), ['Project', 'Annotators']);
    assert.deepEqual(rows.map((r) => r.slice(0, 2)), [['Cats', '4'], ['No project', '1'], ['Project #8', '2']]);
});

test('a project with only technical-account boxes shows zeros, its boxes and a dash where nothing can be averaged', () => {
    // the row as the service sends it: nobody worked in the project, so both ratios are null
    const automated = {
        id: 3,
        user_name: null,
        annotators: 0,
        sessions: 0,
        working_time_ms: 0,
        drawn: 0,
        pasted: 0,
        propagated: 0,
        model: 9,
        saved_boxes: 7,
        alignments: 0,
        class_changes: 0,
        deletions: 0,
        average_create_ms: null,
        hotkey_share: null,
    };
    const shown = details({
        by: 'projects', rows: [row(1, { user_name: null, annotators: 2 }), automated], project_ids: [1, 3], total: 2,
    });
    for (const [answer, expected] of [
        [shown, ['Project #3', '0', '0', '0.0 h', '0', '0', '0', '9', '0', '0', '0', '—', '—']],
        // a legacy period: its saved boxes in place of Model
        [{ ...shown, legacy: true, shapes: 'all' },
            ['Project #3', '0', '0', '0.0 h', '0', '0', '0', '7', '0', 'Not recorded', '0', '—', 'Not recorded']],
    ]) {
        const html = card({ details: answer, by: 'projects' });
        const rows = cells(html);
        assert.equal(rows.length, 3);
        assert.deepEqual(rows[2], expected);
        // no cell is left empty and no figure is the result of a division by zero, hover text included
        assert.ok(rows.every((cellsOfRow) => cellsOfRow.every((cell) => cell !== '')));
        assert.doesNotMatch(html, /NaN|Infinity|undefined|null/);
        assert.match(text(html), /1–2 of 2/);
    }
});

test('a legacy period shows saved boxes in place of Model and says what was not recorded', () => {
    const [header, alice] = cells(card({ details: details({ legacy: true, shapes: 'all' }) }));
    assert.equal(header[7], 'Boxes saved');
    assert.equal(alice[7], '9');
    assert.equal(alice[9], 'Not recorded');
    assert.equal(alice[12], 'Not recorded');
});

test('ten rows a page: which rows are shown, with previous and next', () => {
    const middle = card({ details: details({ page: 2, total: 23, rows: Array.from({ length: 10 }, (_, i) => row(20 + i)) }) });
    assert.match(text(middle), /11–20 of 23/);
    const buttons = [...middle.matchAll(/<button[^>]*>(Previous|Next)<\/button>/g)];
    assert.deepEqual(buttons.map((m) => m[1]), ['Previous', 'Next']);
    assert.ok(buttons.every((m) => !/disabled/.test(m[0])));

    const last = card({ details: details({ page: 3, total: 23, rows: [row(1), row(2), row(3)] }) });
    assert.match(text(last), /21–23 of 23/);
    assert.match(last, /<button[^>]*disabled[^>]*>Next<\/button>/);

    // one page: no paging buttons
    assert.match(text(card()), /1–2 of 2/);
    assert.doesNotMatch(card(), />Previous</);
});

test('a search with no rows says so; an empty period says there was no work', () => {
    assert.match(text(card({ details: details({ total: 0, rows: [] }), search: 'zed' })), /No match for this search\./);
    assert.match(text(card({ details: details({ total: 0, rows: [] }) })), /No job work in this period/);
});

test('a long name is shortened by the column with the full name on hover; the name column stays in place', () => {
    const name = 'a-very-long-annotator-name-that-does-not-fit-in-the-column@example.com';
    const html = card({ details: details({ rows: [row(11, { user_name: name })], total: 1 }) });
    const cell = html.match(/<th[^>]*cvat-team-analytics-details-name[^>]*>.*?<\/th>/g)[1];
    assert.match(cell, new RegExp(`title="${name}"`));
    // the table sits in a sideways scroller and the name cells are the sticky first column
    assert.match(html, /cvat-team-analytics-table-scroll/);
    assert.ok(html.match(/cvat-team-analytics-details-name/g).length >= 2);
});

test('the selected row is marked', () => {
    const html = card({ selected: 12 });
    assert.match(html, /aria-pressed="true"[^>]*title="bob"/);
    assert.match(html, /aria-pressed="false"[^>]*title="alice"/);
});

// A table of a period not wholly processed, as the service sends it: the envelope, and every figure null.
function noFigures(by = 'annotators') {
    return {
        by,
        page: null,
        page_size: 10,
        total: null,
        legacy: false,
        partly_legacy: false,
        cutover: null,
        shapes: 'bounding_boxes',
        processed: false,
        technical_accounts: 1,
        rows: null,
        ...(by === 'projects' ? { project_ids: null } : {}),
    };
}

test('a period that is not processed yet shows no figures', () => {
    for (const by of ['annotators', 'projects']) {
        const html = card({ details: noFigures(by), by });
        assert.match(text(html), /not processed yet/i);
        assert.doesNotMatch(text(html), /NaN|of 0|Previous/);
    }
});

// --- the section: its own requests, search, paging and picking ----------------------------------------------

function params(request) {
    return new URL(request.url, 'http://localhost').searchParams;
}

const PROJECT_IDS = [0, 3, 4, 7];

function detailsAnswer(url) {
    const query = new URL(url, 'http://localhost').searchParams;
    const by = query.get('by');
    const page = Number(query.get('page') || 1);
    if (by === 'projects') {
        const ids = query.has('ids') ? query.get('ids').split(',').filter(Boolean).map(Number) : PROJECT_IDS;
        return {
            body: details({
                by, total: ids.length, project_ids: PROJECT_IDS, rows: ids.map((id) => row(id, { user_name: null, annotators: 1 })),
            }),
        };
    }
    return { body: details({ page, total: 23, rows: Array.from({ length: 10 }, (_, i) => row(100 + i + 10 * (page - 1))) }) };
}

function section(request, props = {}, names = { 3: 'Cats', 4: 'Dogs', 7: 'Hotdogs' }) {
    const Section = loadPage('details-section.tsx', {
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async (ids) => Object.fromEntries(ids.filter((id) => id in names).map((id) => [id, names[id]])) },
    }).default;
    return React.createElement(Section, {
        organization: 'team-org', timeZone: 'UTC', period: 'month', month: '2026-10', project: 3, annotator: null,
        shapes: 'bounding_boxes', ...props,
    });
}

async function click(element) {
    await act(async () => { element.click(); });
}

async function type(container, value) {
    const input = container.querySelector('input[type="search"]');
    await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
}

function button(container, label) {
    return [...container.querySelectorAll('button')].find((b) => b.textContent === label);
}

test('an answer without figures shows the not processed state, by annotator and by project', async () => {
    const { request } = suppliedService((url) => ({ body: noFigures(new URL(url, 'http://localhost').searchParams.get('by')) }));
    const page = await mount(section(request));
    try {
        await page.settle();
        assert.match(page.container.textContent, /This period is not processed yet/);
        await click(button(page.container, 'Projects'));
        await page.settle();
        assert.match(page.container.textContent, /This period is not processed yet/);
        assert.doesNotMatch(page.container.textContent, /could not be/);
    } finally {
        await page.unmount();
    }
});

test('the table asks for the period, filters and shapes, pages with next and narrows by name', async () => {
    const { request, requests } = suppliedService(detailsAnswer);
    const page = await mount(section(request));
    try {
        await page.settle();
        let last = params(requests[requests.length - 1]);
        assert.equal(requests[requests.length - 1].url.split('?')[0], '/api/team-analytics/details');
        assert.deepEqual(Object.fromEntries(last), {
            period: 'month', tz: 'UTC', month: '2026-10', project: '3', shapes: 'bounding_boxes',
            by: 'annotators', page: '1',
        });
        assert.match(page.container.textContent, /1–10 of 23/);
        await click(button(page.container, 'Next'));
        await page.settle();
        assert.equal(params(requests[requests.length - 1]).get('page'), '2');
        assert.match(page.container.textContent, /11–20 of 23/);
        // typing starts again from the first page
        await type(page.container, 'ali');
        await page.settle();
        last = params(requests[requests.length - 1]);
        assert.equal(last.get('search'), 'ali');
        assert.equal(last.get('page'), '1');
    } finally {
        await page.unmount();
    }
});

test('projects are found by the name the page shows, No project included', async () => {
    const { request, requests } = suppliedService(detailsAnswer);
    const page = await mount(section(request));
    try {
        await page.settle();
        await click(button(page.container, 'Projects'));
        await page.settle();
        assert.equal(params(requests[requests.length - 1]).get('by'), 'projects');
        assert.equal(page.container.querySelector('input[type="search"]').getAttribute('aria-label'), 'Find a project');
        await type(page.container, 'DOG');
        await page.settle();
        let last = params(requests[requests.length - 1]);
        assert.equal(last.get('ids'), '4,7');
        assert.equal(last.get('search'), null);
        assert.deepEqual([...page.container.querySelectorAll('tbody th')].map((th) => th.textContent), ['Dogs', 'Hotdogs']);
        await type(page.container, 'no proj');
        await page.settle();
        assert.equal(params(requests[requests.length - 1]).get('ids'), '0');
        await type(page.container, 'zebra');
        await page.settle();
        last = params(requests[requests.length - 1]);
        assert.equal(last.get('ids'), '');
        assert.match(page.container.textContent, /No match for this search\./);
    } finally {
        await page.unmount();
    }
});

test('a project search over thousands of projects asks for one page of ids at a time', async () => {
    // project_ids come in the table's order (most working time first); the page pages the matches itself
    const many = Array.from({ length: 2000 }, (_, index) => 9_000_001 + index);
    const names = Object.fromEntries(many.map((id) => [id, `Shelf ${id}`]));
    const { request, requests } = suppliedService((url) => {
        const query = new URL(url, 'http://localhost').searchParams;
        if (query.get('by') !== 'projects') return detailsAnswer(url);
        const ids = query.has('ids') ? query.get('ids').split(',').filter(Boolean).map(Number) : many.slice(0, 10);
        return {
            body: details({
                by: 'projects', page: 1, total: query.has('ids') ? ids.length : many.length, project_ids: many,
                rows: ids.map((id) => row(id, { user_name: null, annotators: 1 })),
            }),
        };
    });
    const page = await mount(section(request, {}, names));
    try {
        await page.settle();
        await click(button(page.container, 'Projects'));
        await page.settle();
        await type(page.container, 'shelf');
        await page.settle();
        const searches = () => requests.map(params).filter((query) => query.has('ids'));
        for (const query of searches()) {
            assert.ok(query.get('ids').split(',').length <= 10, `ids=${query.get('ids').slice(0, 60)}...`);
        }
        assert.equal(searches().at(-1).get('ids'), many.slice(0, 10).join(','));
        assert.match(page.container.textContent, /1–10 of 2,000/);
        await click(button(page.container, 'Next'));
        await page.settle();
        assert.equal(searches().at(-1).get('ids'), many.slice(10, 20).join(','));
        assert.match(page.container.textContent, /11–20 of 2,000/);
        assert.deepEqual([...page.container.querySelectorAll('tbody th')].map((th) => th.textContent),
            many.slice(10, 20).map((id) => `Shelf ${id}`));
    } finally {
        await page.unmount();
    }
});

test('an unreadable answer leaves a short notice', async () => {
    const { request } = suppliedService(() => ({ body: { by_annotator: { rows: [] } } }));
    const page = await mount(section(request));
    try {
        await page.settle();
        assert.match(page.container.textContent, /Details could not be loaded/);
    } finally {
        await page.unmount();
    }
});

test('clicking a row sets it as the page filter, kept in the address', async () => {
    const { createMemoryHistory } = dependency('history');
    const history = createMemoryHistory({ initialEntries: ['/team-analytics?period=year'] });
    const { request, requests } = suppliedService((url) => {
        if (url.includes('/details?')) return detailsAnswer(url);
        if (url.includes('/status?')) return { body: {} };
        if (url.includes('/trends?')) return { status: 500, body: {} };
        return { body: { by_annotator: { rows: [] } } };
    });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } }, shortcuts: { keyMap: {}, normalizedKeyMap: {} } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    const detailRequests = () => requests.filter((r) => r.url.includes('/details?')).map(params);
    const page = await mount(React.createElement(Page));
    try {
        await page.settle();
        assert.equal(detailRequests()[0].get('period'), 'year');
        await click(page.container.querySelector('.cvat-team-analytics-details-row'));
        await page.settle();
        assert.equal(new URLSearchParams(history.location.search).get('annotator'), '100');
        assert.equal(page.container.querySelector('.cvat-team-analytics-details-row [aria-pressed="true"]').textContent, 'user100');
        // the trends card has a Projects button of its own
        await click(button(page.container.querySelector('[aria-label="Table rows"]'), 'Projects'));
        await page.settle();
        await click(page.container.querySelector('.cvat-team-analytics-details-row'));
        await page.settle();
        const address = new URLSearchParams(history.location.search);
        assert.deepEqual([address.get('project'), address.get('annotator')], ['0', '100']);
        const last = detailRequests()[detailRequests().length - 1];
        // the table by project is narrowed by the annotator filter; its own filter only marks a row
        assert.deepEqual([last.get('by'), last.get('annotator'), last.get('project')], ['projects', '100', null]);
        assert.equal(page.container.querySelector('.cvat-team-analytics-details-row [aria-pressed="true"]').textContent, 'No project');
    } finally {
        await page.unmount();
    }
});

test('picking a row on a later page keeps that page shown', async () => {
    const { request } = suppliedService(detailsAnswer);
    const { type: Section, props } = section(request);
    let picked = null;
    function Holder() {
        const [annotator, setAnnotator] = React.useState(null);
        picked = annotator;
        return React.createElement(Section, { ...props, annotator, onPick: (kind, id) => setAnnotator(id) });
    }
    const page = await mount(React.createElement(Holder));
    try {
        await page.settle();
        await click(button(page.container, 'Next'));
        await page.settle();
        await click(page.container.querySelectorAll('.cvat-team-analytics-details-row')[2]);
        await page.settle();
        assert.equal(picked, 112);
        assert.match(page.container.textContent, /11–20 of 23/);
        assert.equal(page.container.querySelector('.cvat-team-analytics-details-row [aria-pressed="true"]').textContent, 'user112');
    } finally {
        await page.unmount();
    }
});
