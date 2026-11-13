// Projects and filters: working time by project and by annotator with the rest as one line, project
// names from CVAT, and the project and annotator filters driven by clicking rows and kept in the address.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, domAvailable, loadPage, mount, render, suppliedFetch, text,
} = require('./helper.cjs');

const domTest = (name, fn) => test(name, { skip: !domAvailable && 'jsdom is not installed in cvat/node_modules' }, fn);

const View = loadPage('team-analytics-view.tsx').default;
const HOUR = 3600000;

const OVERVIEW = {
    by_annotator: {
        rows: [
            { user_id: 11, user_name: 'alice', working_time_ms: 4 * HOUR },
            { user_id: 12, user_name: 'bob', working_time_ms: 2.5 * HOUR },
        ],
        rest: { count: 0, working_time_ms: 0 },
    },
    by_project: {
        rows: [
            { project_id: 1, working_time_ms: 3.5 * HOUR },
            { project_id: 2, working_time_ms: 2 * HOUR },
            { project_id: 0, working_time_ms: 1 * HOUR },
        ],
        rest: { count: 0, working_time_ms: 0 },
    },
    headline: { annotators: 2, projects: 3 },
    filters: { project: null, annotator: null },
};

// the page address with the given filters (Week)
const address = (project, annotator) => ({
    period: 'week', month: null, project, annotator,
});

function ready(overview = OVERVIEW, props = {}) {
    return { organization: 'team-org', state: { kind: 'ready', overview }, ...props };
}

function card(html, name) {
    const match = html.match(new RegExp(`<section[^>]*cvat-team-analytics-${name}[^>]*>(.*?)</section>`));
    assert.ok(match, `the ${name} card is shown`);
    return match[1];
}

function rows(html, kind) {
    return [...html.matchAll(new RegExp(`<button[^>]*cvat-team-analytics-${kind}-row[^>]*>(.*?)</button>`, 'g'))]
        .map((match) => text(match[1]));
}

test('working time by project lists projects by name, No project for work outside projects', () => {
    const html = render(View, ready(OVERVIEW, { projectNames: { 1: 'Street scenes', 2: 'Retail shelves' } }));
    const projects = card(html, 'working-time-by-project');
    assert.match(text(projects), /^Working time by project/);
    assert.deepEqual(rows(projects, 'project'), ['Street scenes 3.5 h', 'Retail shelves 2.0 h', 'No project 1.0 h']);
});

test('a project CVAT does not return to the viewer stays in the figures, shown by its identifier', () => {
    const html = render(View, ready(OVERVIEW, { projectNames: { 1: 'Street scenes' } }));
    assert.deepEqual(rows(card(html, 'working-time-by-project'), 'project'),
        ['Street scenes 3.5 h', 'Project #2 2.0 h', 'No project 1.0 h']);
});

test('each chart shows its rows and one line with the count and total of the rest', () => {
    const overview = {
        ...OVERVIEW,
        by_annotator: { rows: OVERVIEW.by_annotator.rows, rest: { count: 92, working_time_ms: 120.25 * HOUR } },
        by_project: { rows: OVERVIEW.by_project.rows, rest: { count: 1, working_time_ms: 0.5 * HOUR } },
    };
    const html = render(View, ready(overview));
    assert.match(text(card(html, 'working-time-by-annotator')), /92 more, not shown 120\.3 h$/);
    assert.match(text(card(html, 'working-time-by-project')), /1 more, not shown 0\.5 h$/);
    assert.doesNotMatch(text(card(render(View, ready()), 'working-time-by-project')), /more, not shown/);
});

test('each chart carries its legend inside the card', () => {
    const html = render(View, ready());
    for (const name of ['working-time-by-project', 'working-time-by-annotator']) {
        assert.match(card(html, name), /cvat-team-analytics-legend[^>]*>.*Working time/);
    }
});

test('a long name is shortened by the layout with the full name on hover', () => {
    const long = 'Pedestrian crossings in winter, night shots from the northern district, second batch';
    const html = render(View, ready(OVERVIEW, { projectNames: { 1: long } }));
    assert.match(card(html, 'working-time-by-project'), new RegExp(`class="cvat-team-analytics-name" title="${long}"`));
});

test('the headline shows active annotators and across how many projects', () => {
    const headline = (html) => text(card(html, 'annotators'));
    assert.equal(headline(render(View, ready())), 'Active annotators 2 across 3 projects');
    assert.equal(headline(render(View, ready({ ...OVERVIEW, headline: { annotators: 1, projects: 1 } }))),
        'Active annotators 1 across 1 project');
    const filtered = {
        ...OVERVIEW,
        headline: { annotators: 1, projects: 2 },
        by_annotator: { ...OVERVIEW.by_annotator, rest: { count: 3, working_time_ms: HOUR } },
    };
    assert.equal(headline(render(View, ready(filtered, { address: address(null, 12) }))),
        'Active annotators 1 of 5 across 2 projects');
    assert.equal(headline(render(View, ready(OVERVIEW, { address: address(1, null) }))),
        'Active annotators 2 worked in the selected project');
});

function chips(html) {
    const match = html.match(/<div class="cvat-team-analytics-filter-chips">(.*?)<\/div>/);
    assert.ok(match, 'the filter row shows the project and annotator filters');
    return text(match[1]);
}

test('the filter row names the selected project and annotator, the selected rows are marked', () => {
    const overview = { ...OVERVIEW, filters: { project: 0, annotator: { user_id: 40, user_name: 'zoe' } } };
    const html = render(View, ready(overview, {
        address: address(0, 40), onAddressChange() {}, projectNames: {},
    }));
    assert.equal(chips(html), 'Project No project × Annotator zoe ×');
    assert.match(card(html, 'working-time-by-project'), /aria-pressed="true"[^>]*title="No project: 1\.00 h"/);
    assert.equal(chips(render(View, ready(OVERVIEW, { address: address(null, null), onAddressChange() {} }))),
        'Project All projects Annotator All annotators');
});

test('project names come from the CVAT API through cvat-core, one request for the wanted projects', async () => {
    const asked = [];
    const core = {
        projects: {
            async get(filter) {
                asked.push(filter);
                // CVAT returns only the projects the viewer may see: 9 was deleted or is not visible
                return Object.assign([{ id: 1, name: 'Street scenes' }, { id: 2, name: 'Retail shelves' }], { count: 2 });
            },
        },
    };
    const { lookupProjectNames } = loadPage('project-names.ts', { 'cvat-core-wrapper': { getCore: () => core } });

    assert.deepEqual(await lookupProjectNames([2, 0, 1, 9, 2]), { 1: 'Street scenes', 2: 'Retail shelves' });
    assert.deepEqual(asked, [{ filter: JSON.stringify({ in: [{ var: 'id' }, [2, 1, 9]] }), pageSize: 3 }]);
    assert.deepEqual(await lookupProjectNames([0]), {}, 'No project needs no request');
    assert.equal(asked.length, 1);
});

// --- the mounted page: filters in the address, names from CVAT -----------------------------------

const { createMemoryHistory } = dependency('history');

function mountPage({ search = '', names = async () => ({}), answer = () => ({ body: OVERVIEW }) } = {}) {
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const { fetch, requests } = suppliedFetch(answer);
    const lookups = [];
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), fetchService: fetch },
        './project-names': {
            lookupProjectNames: async (ids) => { lookups.push(ids); return names(ids); },
        },
    }).default;
    return {
        history, requests, lookups, Page,
    };
}

const filterParams = (request) => {
    const params = new URL(request.url, 'http://localhost').searchParams;
    return [params.get('project'), params.get('annotator')];
};

async function click(element) {
    await act(async () => { element.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
}

function rowNamed(container, kind, name) {
    const row = [...container.querySelectorAll(`.cvat-team-analytics-${kind}-row`)]
        .find((element) => element.querySelector('.cvat-team-analytics-name').textContent === name);
    assert.ok(row, `a ${kind} row named ${name}`);
    return row;
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

domTest('clicking a row filters the whole page; clicking it again or the clear control removes it', async () => {
    const { history, requests, Page } = mountPage({ names: async () => ({ 1: 'Street scenes', 2: 'Retail shelves' }) });
    await opened(Page, async (view) => {
        assert.deepEqual(filterParams(requests.at(-1)), [null, null]);

        await click(rowNamed(view.container, 'project', 'Retail shelves'));
        await view.settle();
        assert.equal(history.location.search, '?project=2&period=week');
        assert.deepEqual(filterParams(requests.at(-1)), ['2', null]);
        assert.match(view.container.querySelector('.cvat-team-analytics-filter-project').textContent, /Retail shelves/);

        await click(rowNamed(view.container, 'annotator', 'bob'));
        await view.settle();
        assert.equal(history.location.search, '?project=2&period=week&annotator=12');
        assert.deepEqual(filterParams(requests.at(-1)), ['2', '12'], 'the two filters combine');

        await click(rowNamed(view.container, 'project', 'Retail shelves'));
        await view.settle();
        assert.equal(history.location.search, '?period=week&annotator=12');

        await click(view.container.querySelector('.cvat-team-analytics-filter-annotator .cvat-team-analytics-filter-clear'));
        await view.settle();
        assert.equal(history.location.search, '?period=week');
        assert.deepEqual(filterParams(requests.at(-1)), [null, null]);

        await act(async () => { history.goBack(); });
        await view.settle();
        assert.equal(history.location.search, '?period=week&annotator=12', 'Back restores the previous filter');
        assert.deepEqual(filterParams(requests.at(-1)), [null, '12']);
    });
});

domTest('a shared address opens with its filters; a filter change keeps the period and other keys', async () => {
    const overview = { ...OVERVIEW, filters: { project: 0, annotator: { user_id: 40, user_name: 'zoe' } } };
    const { history, requests, Page } = mountPage({
        search: '?period=month&month=2026-10&project=0&annotator=40&tab=x', answer: () => ({ body: overview }),
    });
    await opened(Page, async (view) => {
        assert.deepEqual(filterParams(requests[0]), ['0', '40']);
        assert.equal(view.container.querySelector('.cvat-team-analytics-filter-chips').textContent,
            'ProjectNo project×Annotatorzoe×');
        await click(view.container.querySelector('.cvat-team-analytics-filter-project .cvat-team-analytics-filter-clear'));
        await view.settle();
        assert.equal(history.location.search, '?period=month&month=2026-10&annotator=40&tab=x');
        const params = new URL(requests.at(-1).url, 'http://localhost').searchParams;
        assert.deepEqual([params.get('period'), params.get('month'), params.get('project'), params.get('annotator')],
            ['month', '2026-10', null, '40']);
    });
});

domTest('project names are asked of CVAT for the shown and selected projects; a failed lookup shows identifiers', async () => {
    const { lookups, Page } = mountPage({ search: '?project=7', names: async () => { throw new Error('403'); } });
    await opened(Page, async (view) => {
        assert.deepEqual([...lookups.at(-1)].sort(), [1, 2, 7]);
        assert.deepEqual([...view.container.querySelectorAll('.cvat-team-analytics-project-row .cvat-team-analytics-name')]
            .map((element) => element.textContent), ['Project #1', 'Project #2', 'No project']);
        assert.match(view.container.querySelector('.cvat-team-analytics-filter-project').textContent, /Project #7/);
    });
});
