// Projects and filters: working time by project and by annotator with the rest as one line, project
// names from CVAT, and the project and annotator filters driven by clicking rows and kept in the address.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

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
        // the split's colours (split-bars.test.cjs)
        assert.match(card(html, name), /cvat-team-analytics-breakdown-legend[^>]*>.*Creation.*Other/);
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

test('names of thousands of projects are asked in bounded requests; a failed one leaves only its own unnamed', async () => {
    const asked = [];
    const core = {
        projects: {
            async get({ filter, pageSize }) {
                const ids = JSON.parse(filter).in[1];
                asked.push({ ids, pageSize, url: `/api/projects?filter=${encodeURIComponent(filter)}&page_size=${pageSize}` });
                if (ids.includes(1500)) throw new Error('request rejected');
                return Object.assign(ids.map((id) => ({ id, name: `Project ${id}` })), { count: ids.length });
            },
        },
    };
    const { lookupProjectNames } = loadPage('project-names.ts', { 'cvat-core-wrapper': { getCore: () => core } });
    const ids = Array.from({ length: 2000 }, (_, index) => 9_000_001 + index);
    ids[1499] = 1500;

    const names = await lookupProjectNames(ids);

    assert.ok(asked.length > 1);
    for (const request of asked) {
        assert.ok(request.url.length < 4096, `a request line of ${request.url.length} characters`);
        assert.ok(request.pageSize >= request.ids.length && request.pageSize <= 500);
    }
    assert.deepEqual(asked.flatMap((request) => request.ids).sort(), [...ids].sort(), 'every id asked once');
    const failed = asked.find((request) => request.ids.includes(1500)).ids;
    assert.equal(Object.keys(names).length, ids.length - failed.length);
    assert.equal(names[9_000_001], 'Project 9000001');
});

// --- the mounted page: filters in the address, names from CVAT -----------------------------------

const { createMemoryHistory } = dependency('history');

function mountPage({
    search = '', names = async () => ({}), answer = () => ({ body: OVERVIEW }), organization = 'team-org',
} = {}) {
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const { request, requests } = suppliedService(answer);
    const lookups = [];
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': {
            useSelector: (select) => select({ organizations: { current: organization ? { slug: organization } : null } }),
        },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
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

test('clicking a row filters the whole page; clicking it again or the clear control removes it', async () => {
    const { history, requests, Page } = mountPage({ names: async () => ({ 1: 'Street scenes', 2: 'Retail shelves' }) });
    await opened(Page, async (view) => {
        assert.deepEqual(filterParams(requests.at(-1)), [null, null]);

        await click(rowNamed(view.container, 'project', 'Retail shelves'));
        await view.settle();
        assert.equal(history.location.search, '?project=2&org=team-org&period=week');
        assert.deepEqual(filterParams(requests.at(-1)), ['2', null]);
        assert.match(view.container.querySelector('.cvat-team-analytics-filter-project').textContent, /Retail shelves/);

        await click(rowNamed(view.container, 'annotator', 'bob'));
        await view.settle();
        assert.equal(history.location.search, '?project=2&org=team-org&period=week&annotator=12');
        assert.deepEqual(filterParams(requests.at(-1)), ['2', '12'], 'the two filters combine');

        await click(rowNamed(view.container, 'project', 'Retail shelves'));
        await view.settle();
        assert.equal(history.location.search, '?org=team-org&period=week&annotator=12');

        await click(view.container.querySelector('.cvat-team-analytics-filter-annotator .cvat-team-analytics-filter-clear'));
        await view.settle();
        assert.equal(history.location.search, '?period=week');
        assert.deepEqual(filterParams(requests.at(-1)), [null, null]);

        await act(async () => { history.goBack(); });
        await view.settle();
        assert.equal(history.location.search, '?org=team-org&period=week&annotator=12', 'Back restores the previous filter');
        assert.deepEqual(filterParams(requests.at(-1)), [null, '12']);
    });
});

test('a shared address opens with its filters; a filter change keeps the period and other keys', async () => {
    const overview = { ...OVERVIEW, filters: { project: 0, annotator: { user_id: 40, user_name: 'zoe' } } };
    const { history, requests, Page } = mountPage({
        search: '?period=month&month=2026-10&project=0&annotator=40&org=team-org&tab=x', answer: () => ({ body: overview }),
    });
    await opened(Page, async (view) => {
        assert.deepEqual(filterParams(requests[0]), ['0', '40']);
        assert.equal(view.container.querySelector('.cvat-team-analytics-filter-chips').textContent,
            'ProjectNo project×Annotatorzoe×');
        await click(view.container.querySelector('.cvat-team-analytics-filter-project .cvat-team-analytics-filter-clear'));
        await view.settle();
        assert.equal(history.location.search, '?period=month&month=2026-10&annotator=40&org=team-org&tab=x');
        const params = new URL(requests.at(-1).url, 'http://localhost').searchParams;
        assert.deepEqual([params.get('period'), params.get('month'), params.get('project'), params.get('annotator')],
            ['month', '2026-10', null, '40']);
    });
});

test('project names are asked of CVAT for the shown and selected projects; a failed lookup shows identifiers', async () => {
    const { lookups, Page } = mountPage({ search: '?project=7&org=team-org', names: async () => { throw new Error('403'); } });
    await opened(Page, async (view) => {
        assert.deepEqual([...lookups.at(-1)].sort(), [1, 2, 7]);
        assert.deepEqual([...view.container.querySelectorAll('.cvat-team-analytics-project-row .cvat-team-analytics-name')]
            .map((element) => element.textContent), ['Project #1', 'Project #2', 'No project']);
        assert.match(view.container.querySelector('.cvat-team-analytics-filter-project').textContent, /Project #7/);
    });
});

// the last overview request (trends, details and status requests carry the filters too)
const lastOverview = (requests) => requests.filter((request) => request.url.includes('/overview?')).at(-1);

// Filters belong to the organization they were picked in: the address names it (`org`), and filters of
// another organization, or of an address that names none, are never applied to the current one.
test('filters picked in one organization are not applied in another', async () => {
    const { history, requests, Page } = mountPage({ search: '?period=week&project=5&annotator=12&org=org-a' });
    await opened(Page, async (view) => {
        assert.deepEqual(filterParams(lastOverview(requests)), [null, null]);
        const chips = view.container.querySelector('.cvat-team-analytics-filter-chips').textContent;
        assert.match(chips, /All projects/);
        assert.match(chips, /All annotators/);

        // a filter picked now belongs to the current organization
        await click(rowNamed(view.container, 'annotator', 'bob'));
        await view.settle();
        const address = new URLSearchParams(history.location.search);
        assert.equal(address.get('org'), 'team-org');
        assert.equal(address.get('project'), null);
        assert.deepEqual(filterParams(lastOverview(requests)), [null, '12']);
    });
});

test('an address with filters but no organization applies them only without an organization', async () => {
    const underOrganization = mountPage({ search: '?project=5&annotator=12' });
    await opened(underOrganization.Page, async () => {
        assert.deepEqual(filterParams(lastOverview(underOrganization.requests)), [null, null]);
    });
    const instance = mountPage({ search: '?project=5&annotator=12', organization: null });
    await opened(instance.Page, async () => {
        assert.deepEqual(filterParams(lastOverview(instance.requests)), ['5', '12']);
    });
    const own = mountPage({ search: '?project=5&org=team-org' });
    await opened(own.Page, async () => {
        assert.deepEqual(filterParams(lastOverview(own.requests)), ['5', null], 'a link of the same organization keeps its filter');
    });
});
