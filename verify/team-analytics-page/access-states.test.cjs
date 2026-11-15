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

const ROLES = /This page is for administrators and for owners and maintainers of the current organization\./;

test('an ordinary annotator without an organization sees that the page is not available and for whom', async () => {
    const { text, requests } = await visit(null, { status: 403, body: { error: 'forbidden' } });
    assert.equal(new URL(requests[0].url, 'http://localhost').searchParams.get('org'), null);
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(text, /Select an organization/);
    assert.doesNotMatch(text, /All organizations and personal workspaces/);
});

test('a worker or supervisor of the selected organization sees that the page is not available', async () => {
    const { text, html } = await visit('team-org', { status: 403, body: { error: 'forbidden' } });
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(html, /cvat-team-analytics-error/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});

test('an owner or maintainer without an organization is asked to select one, with no scope claimed', async () => {
    const { text, html } = await visit(null, { status: 403, body: { error: 'organization_required' } });
    assert.ok(html.includes('cvat-team-analytics-select-organization'));
    assert.match(text, /Select an organization/);
    assert.match(text, /No organization selected/);
    assert.doesNotMatch(text, /All organizations and personal workspaces/);
    assert.doesNotMatch(text, /not available/);
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
