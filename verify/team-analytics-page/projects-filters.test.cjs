// Projects and filters: working time by project and by annotator with the rest as one line, project
// names from the fork's API, and the project and annotator filters driven by clicking rows and kept in the address.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadCoreExceptions, loadPage, mount, render, suppliedService, text,
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
    // the two selectors' wrappers end the row
    const match = html.match(/<div class="cvat-team-analytics-filter-chips">(.*?)<\/div><\/div>/);
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

test('project names come from the fork\'s API (GET project-names), one request for the wanted projects', async () => {
    // the API names any existing project whatever its organization: 9 does not exist
    const { request, requests } = suppliedService(() => ({ body: { names: { 1: 'Street scenes', 2: 'Retail shelves' } } }));
    const { lookupProjectNames } = loadPage('project-names.ts');

    assert.deepEqual(await lookupProjectNames([2, 0, 1, 9, 2], request), { 1: 'Street scenes', 2: 'Retail shelves' });
    assert.deepEqual(requests.map((sent) => [sent.endpoint, sent.params]), [['project-names', { ids: '2,1,9' }]]);
    assert.deepEqual(await lookupProjectNames([0], request), {}, 'No project needs no request');
    assert.equal(requests.length, 1);
});

test('the real boundary asks cvat-core for /api/team-analytics/project-names with GET', async () => {
    const calls = [];
    const core = {
        config: { backendAPI: '/api' },
        server: {
            async request(url, data) {
                calls.push({ url, data });
                return { status: 200, data: { names: { 4: 'Alpha' } } };
            },
        },
    };
    const { ServerError } = loadCoreExceptions();
    const boundaries = { 'cvat-core-wrapper': { getCore: () => core, ServerError } };
    const { lookupProjectNames } = loadPage('project-names.ts', boundaries);
    assert.deepEqual(await lookupProjectNames([4, 8]), { 4: 'Alpha' });
    assert.deepEqual(calls, [{ url: '/api/team-analytics/project-names', data: { method: 'GET', params: { ids: '4,8' } } }]);
});

test('names of thousands of projects are asked in requests of at most 500 ids and a request line under 4096 characters; a failed one leaves only its own unnamed', async () => {
    const { request, requests } = suppliedService((url, sent) => {
        const ids = sent.params.ids.split(',').map(Number);
        if (ids.includes(1500)) return { status: 400, body: { error: 'bad_request', detail: 'rejected' } };
        return { body: { names: Object.fromEntries(ids.map((id) => [id, `Project ${id}`])) } };
    });
    const { lookupProjectNames } = loadPage('project-names.ts');
    // long ids: the length of the request line ends each request before the count does
    const ids = Array.from({ length: 2000 }, (_, index) => 9_000_001 + index);
    ids[1499] = 1500;

    const answered = new Set();
    const names = await lookupProjectNames(ids, request, answered);

    const asked = requests.map((sent) => sent.params.ids.split(',').map(Number));
    // the failed request's ids are not reported as answered: the page asks them again
    assert.equal(answered.has(1500), false);
    assert.equal(answered.size, ids.length - asked.find((chunk) => chunk.includes(1500)).length);
    for (const [index, sent] of requests.entries()) {
        assert.ok(asked[index].length <= 500, `${asked[index].length} ids in one request`);
        // the address as sent, its commas encoded; the request line adds the method, the version and `org`
        assert.ok(sent.url.length < 3900, `a request line of ${sent.url.length} characters`);
    }
    assert.equal(requests.length, 7, 'about 300 ids of seven digits per request');
    assert.deepEqual(asked.flat().sort(), [...ids].sort(), 'every id asked once');
    const failed = asked.find((chunk) => chunk.includes(1500));
    assert.equal(Object.keys(names).length, ids.length - failed.length);
    assert.equal(names[9_000_001], 'Project 9000001');
});

test('short ids are asked 500 at a time', async () => {
    const { request, requests } = suppliedService((url, sent) => ({
        body: { names: Object.fromEntries(sent.params.ids.split(',').map((id) => [id, `Project ${id}`])) },
    }));
    const { lookupProjectNames } = loadPage('project-names.ts');
    await lookupProjectNames(Array.from({ length: 600 }, (_, index) => index + 1), request);
    assert.deepEqual(requests.map((sent) => sent.params.ids.split(',').length), [500, 100]);
    for (const sent of requests) assert.ok(sent.url.length < 3900, `a request line of ${sent.url.length} characters`);
});

test('a lookup whose every request fails throws, so the page shows identifiers', async () => {
    const { request } = suppliedService(() => ({ status: 403, body: null }));
    const { lookupProjectNames } = loadPage('project-names.ts');
    await assert.rejects(lookupProjectNames([3], request));
});

// --- the mounted page: filters in the address, names from the fork's API ------------------------

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
            // as the real lookup: the ids of an answered lookup go into `answered`, those of a failed one do not
            lookupProjectNames: async (ids, request, answered) => {
                lookups.push(ids);
                // `names` may itself record a partly answered lookup in `answered` and then throw
                const found = await names(ids, answered);
                ids.forEach((id) => answered?.add(id));
                return found;
            },
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

test('project names are asked for the shown and selected projects; a failed lookup shows identifiers', async () => {
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

test('ids the names lookup did not name are not asked again until the data is reloaded', async () => {
    // project 2 no longer exists: the lookup answers without it
    const projects = { by: 'projects', legacy: false, shapes: 'all', total: { count: 2, working_time_ms: HOUR },
        rows: [1, 2].map((id) => ({ id, user_name: null, working_time_ms: HOUR })) };
    const { history, lookups, Page } = mountPage({
        names: async () => ({ 1: 'Street scenes' }),
        answer: (url) => ({ body: url.includes('/list?') ? projects : OVERVIEW }),
    });
    await opened(Page, async (view) => {
        assert.deepEqual([...lookups[0]].sort(), [1, 2]);
        await act(async () => { history.push('/team-analytics?project=7&org=team-org'); });
        await view.settle();
        assert.deepEqual(lookups.at(-1), [7], 'project 2 is not asked again');
        await click(view.container.querySelector('.cvat-team-analytics-filter-project .cvat-team-analytics-filter-button'));
        await view.settle();
        assert.ok(lookups.flat().filter((id) => id === 2).length === 1, `asked once: ${JSON.stringify(lookups)}`);
    });
});

test('a lookup that throws still remembers the ids of its answered request without names', async () => {
    let first = true;
    const { history, lookups, Page } = mountPage({
        // project 1's request was answered with no name, project 2's failed: the lookup throws
        names: async (ids, answered) => {
            if (!first) return {};
            first = false;
            answered?.add(1);
            throw new Error('503');
        },
    });
    await opened(Page, async (view) => {
        assert.deepEqual([...lookups[0]].sort(), [1, 2]);
        await act(async () => { history.push('/team-analytics?project=7&org=team-org'); });
        await view.settle();
        assert.deepEqual([...lookups.at(-1)].sort(), [2, 7], 'project 1 is not asked again, project 2 is');
    });
});

test('the real lookup reports an answered request without names even when it throws', async () => {
    // seven-digit ids: about 300 per request, so 400 ids are two requests; the second one fails
    const ids = Array.from({ length: 400 }, (_, index) => 9_000_001 + index);
    const { request, requests } = suppliedService((url, sent) => (sent.params.ids.includes(String(ids[399])) ?
        { status: 503, body: null } : { body: { names: {} } }));
    const { lookupProjectNames } = loadPage('project-names.ts');
    const answered = new Set();
    await assert.rejects(lookupProjectNames(ids, request, answered));
    assert.equal(requests.length, 2);
    const firstChunk = requests[0].params.ids.split(',').map(Number);
    assert.deepEqual([...answered], firstChunk, 'the answered request\'s ids, not the failed one\'s');
});

test('ids of a names lookup that failed are asked again', async () => {
    let fail = true;
    const { history, lookups, Page } = mountPage({
        names: async () => {
            if (fail) throw new Error('503');
            return { 1: 'Street scenes' };
        },
    });
    await opened(Page, async (view) => {
        assert.deepEqual([...lookups[0]].sort(), [1, 2]);
        fail = false;
        await act(async () => { history.push('/team-analytics?project=7&org=team-org'); });
        await view.settle();
        assert.deepEqual([...lookups.at(-1)].sort(), [1, 2, 7], 'not remembered as unnamed');
    });
});
