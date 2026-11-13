// How fresh the figures are: the time of the last successful refresh, and a warning once it is
// more than thirty minutes old (the service decides by its own clock).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, domAvailable, loadPage, mount, render, suppliedFetch, text,
} = require('./helper.cjs');

const domTest = (name, fn) => test(name, { skip: !domAvailable && 'jsdom is not installed in cvat/node_modules' }, fn);

const View = loadPage('team-analytics-view.tsx').default;
const READY = { kind: 'ready', overview: { by_annotator: { rows: [] } } };

function refresh(overrides = {}) {
    return {
        last_success_at: '2026-11-13T15:20:00+00:00',
        now: '2026-11-13T15:30:00+00:00',
        interval_s: 600,
        stale_after_s: 1800,
        stale: false,
        ...overrides,
    };
}

function page(status, timeZone = 'Europe/Berlin', state = READY) {
    return text(render(View, {
        organization: 'team-org',
        state,
        address: { period: 'week', month: null },
        onAddressChange() {},
        status,
        timeZone,
    }));
}

test('shows the time of the last successful refresh in the viewer time zone', () => {
    assert.match(page({ refresh: refresh() }), /Data as of 16:20 · refreshed every 10 min/);
    assert.match(page({ refresh: refresh() }, 'America/New_York'), /Data as of 10:20/);
    assert.doesNotMatch(page({ refresh: refresh() }), /more than 30 minutes ago/);
});

test('warns once the last refresh is more than thirty minutes old', () => {
    const shown = page({ refresh: refresh({ now: '2026-11-13T15:51:00+00:00', stale: true }) });
    assert.match(shown, /Data as of 16:20/);
    assert.match(shown, /The figures were last refreshed at 16:20, more than 30 minutes ago\./);
});

test('a refresh on an earlier day names the day', () => {
    const shown = page({
        refresh: refresh({ last_success_at: '2026-11-12T09:05:00+00:00', stale: true }),
    }, 'UTC');
    assert.match(shown, /Data as of Nov 12, 09:05/);
    assert.match(shown, /last refreshed at Nov 12, 09:05/);
});

test('before the first refresh the page says so and warns', () => {
    const shown = page({ refresh: refresh({ last_success_at: null, stale: true }) });
    assert.match(shown, /Not refreshed yet/);
    assert.match(shown, /The figures have not been refreshed yet\./);
});

test('without a status answer no time is claimed', () => {
    assert.doesNotMatch(page(null), /Data as of|refreshed/);
});

domTest('the page reads the status of the selected organization once the figures are shown', async () => {
    const { fetch, requests } = suppliedFetch((url) => (url.includes('/status') ?
        { body: { refresh: refresh({ stale: true, now: '2026-11-13T16:00:00+00:00' }) } } :
        { body: { by_annotator: { rows: [] } } }));
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), fetchService: fetch },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const status = requests.find((request) => request.url.includes('/status'));
    assert.ok(status, 'status is requested');
    const url = new URL(status.url, 'http://localhost');
    assert.equal(url.pathname, '/team-analytics-api/v1/status');
    assert.equal(url.searchParams.get('org'), 'team-org');
    assert.equal(status.init.credentials, 'same-origin');
    assert.ok(view.container.querySelector('.cvat-team-analytics-stale'));
    await view.unmount();
});

domTest('a refused caller is not asked about freshness', async () => {
    const { fetch, requests } = suppliedFetch(() => ({ status: 403, body: { error: 'forbidden' } }));
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), fetchService: fetch },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    assert.equal(requests.filter((request) => request.url.includes('/status')).length, 0);
    await view.unmount();
});
