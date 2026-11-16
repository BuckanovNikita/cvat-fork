// Each refusal of the analytics service, as the page shows it (mounted in jsdom, supplied answers).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, loadPage, mount, suppliedService,
} = require('./helper.cjs');

async function visit(organization, answer) {
    const { request, requests } = suppliedService(() => answer);
    const state = { organizations: { current: organization ? { slug: organization } : null } };
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select(state) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const text = view.container.textContent.replace(/\s+/g, ' ');
    const html = view.container.innerHTML;
    await view.unmount();
    return { text, html, requests };
}

const ROLES = /This page is for administrators of this CVAT instance\./;

test('an ordinary annotator without an organization sees that the page is not available and for whom', async () => {
    const { text, requests } = await visit(null, { status: 403, body: { error: 'forbidden' } });
    assert.equal(new URL(requests[0].url, 'http://localhost').searchParams.get('org'), null);
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(text, /Select an organization/);
    assert.doesNotMatch(text, /All organizations and personal workspaces/);
});

test('anyone but an administrator, an owner or maintainer of the selected organization too, sees the denied state', async () => {
    const { text, html } = await visit('team-org', { status: 403, body: { error: 'forbidden' } });
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(html, /cvat-team-analytics-error/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});

test('a 403 is the denied state whatever its body: there is no "select an organization" state', async () => {
    for (const body of [{ error: 'organization_required' }, null, 'Forbidden']) {
        // eslint-disable-next-line no-await-in-loop
        const { text, html } = await visit(null, { status: 403, body });
        assert.ok(html.includes('cvat-team-analytics-denied'));
        assert.match(text, ROLES);
        assert.doesNotMatch(text, /Select an organization|No organization selected/);
        assert.doesNotMatch(text, /All organizations and personal workspaces/);
    }
});

test('an administrator reads organization scope with an organization selected and instance scope with none', async () => {
    const ready = { status: 200, body: { by_annotator: { rows: [] } } };
    assert.match((await visit('team-org', ready)).text, /Organization team-org · annotation work inside jobs/);
    assert.match((await visit(null, ready)).text, /All organizations and personal workspaces · annotation work inside jobs/);
});

test('an ended session asks to sign in again instead of naming the roles', async () => {
    const { text, html } = await visit('team-org', { status: 401, body: { error: 'not_authenticated' } });
    assert.ok(html.includes('cvat-team-analytics-signed-out'));
    assert.match(text, /Sign in again/);
    assert.doesNotMatch(text, ROLES);
});

test('when CVAT cannot be reached behind the service the page shows the error panel, no figures', async () => {
    const { text, html } = await visit('team-org', { status: 503, body: { error: 'cvat_unavailable' } });
    assert.ok(html.includes('cvat-team-analytics-error'));
    assert.match(text, /Team analytics could not be loaded/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});

test('a 404 (analytics switched off, or an unknown organization) shows that the page is not available', async () => {
    const { text, html } = await visit('team-org', { status: 404, body: null });
    assert.match(text, /Team analytics is not available/);
    assert.doesNotMatch(html, /cvat-team-analytics-error/);
    assert.doesNotMatch(text, /Select an organization/);
});

test('a 429 that outlived cvat-core\'s retries shows the error panel, no refusal', async () => {
    const { text, html } = await visit('team-org', { status: 429, body: null });
    assert.ok(html.includes('cvat-team-analytics-error'));
    assert.match(text, /Team analytics could not be loaded/);
    assert.doesNotMatch(text, /not available/);
});

// A refusal from any request of an open page, not only the overview, replaces the figures with the refusal.
const READY = { by_annotator: { rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 7200000 }] } };

async function visitOpenPage(answers, search = '') {
    const { request, requests } = suppliedService((url) => {
        const endpoint = new URL(url, 'http://localhost').pathname.split('/').pop();
        return answers[endpoint] ?? { status: 200, body: endpoint === 'overview' ? READY : {} };
    });
    const state = { organizations: { current: { slug: 'team-org' } } };
    const history = { location: { pathname: '/team-analytics', search }, push() {} };
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select(state) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        return {
            text: view.container.textContent.replace(/\s+/g, ' '),
            html: view.container.innerHTML,
            endpoints: requests.map((request) => new URL(request.url, 'http://localhost').pathname.split('/').pop()),
        };
    } finally {
        await view.unmount();
    }
}

test('a refusal of the trends, details, list or status request takes the whole page to that refusal', async (t) => {
    const cases = [
        ['trends', { status: 403, body: { error: 'forbidden' } }, '', /Team analytics is not available/],
        ['details', { status: 401, body: { error: 'not_authenticated' } }, '', /Sign in again/],
        ['status', { status: 401, body: { error: 'not_authenticated' } }, '', /Sign in again/],
        ['list', { status: 403, body: { error: 'forbidden' } }, '?view=annotators', /Team analytics is not available/],
    ];
    for (const [endpoint, answer, search, shown] of cases) {
        // eslint-disable-next-line no-await-in-loop
        await t.test(endpoint, async () => {
            const page = await visitOpenPage({ [endpoint]: answer }, search);
            assert.ok(page.endpoints.includes(endpoint), `the page asked ${endpoint}: ${page.endpoints}`);
            assert.match(page.text, shown);
            assert.doesNotMatch(page.text, /alice/);
            assert.doesNotMatch(page.html, /cvat-team-analytics-annotator-row/);
        });
    }
});

test('a trends request that fails without a refusal keeps the figures shown', async () => {
    const page = await visitOpenPage({ trends: { status: 503, body: { error: 'cvat_unavailable' } } });
    assert.match(page.text, /alice/);
    assert.match(page.text, /Trends could not be loaded/);
    assert.doesNotMatch(page.text, /not available/);
});

// --- the signed-in account: only an administrator's page asks the API anything ---------------------------------

const { dependency } = require('./helper.cjs');

const { createMemoryHistory } = dependency('history');

async function visitAs(auth, search = '') {
    const { request, requests } = suppliedService(() => ({ status: 200, body: READY }));
    const settings = [];
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const store = { auth, organizations: { current: { slug: 'team-org' } } };
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select(store) },
        'react-router': { useHistory: () => history },
        './service': {
            ...loadPage('service.ts'),
            requestService: request,
            requestSettings: async (method) => { settings.push(method); return { status: 200, body: {} }; },
        },
    }).default;
    const view = await mount(React.createElement(Page));
    try {
        // what the first render shows, before any answer could arrive
        const first = view.container.innerHTML;
        await view.settle();
        return {
            first, html: view.container.innerHTML, text: view.container.textContent.replace(/\s+/g, ' '), requests, settings,
        };
    } finally {
        await view.unmount();
    }
}

test('a non-administrator gets the "not available" panel at once and the page asks the API nothing', async () => {
    const accounts = [
        { user: { username: 'owner', groups: ['user'] } },
        { user: { username: 'worker', groups: ['worker'] } },
        { user: null },
    ];
    for (const auth of accounts) {
        // eslint-disable-next-line no-await-in-loop
        const page = await visitAs(auth, '?project=7&annotator=3&org=team-org&view=annotators');
        assert.match(page.first, /cvat-team-analytics-denied/, 'on the first render');
        assert.match(page.text, ROLES);
        assert.deepEqual(page.requests, [], 'no overview, status, list or project-names request');
        assert.deepEqual(page.settings, [], 'no settings request');
        for (const control of ['cvat-team-analytics-settings-button', 'cvat-team-analytics-filters',
            'cvat-team-analytics-header', 'ant-spin']) {
            assert.doesNotMatch(page.first, new RegExp(control), `${control} is never shown`);
        }
        assert.doesNotMatch(page.text, /All organizations and personal workspaces|Organization team-org/);
    }
});

test('an administrator keeps the header controls while the first answer loads', async () => {
    const page = await visitAs({ user: { username: 'admin', groups: ['admin'] } });
    assert.match(page.first, /cvat-team-analytics-settings-button/);
    assert.match(page.first, /cvat-team-analytics-filters/);
    assert.ok(page.requests.some((sent) => sent.endpoint === 'overview'));
});
