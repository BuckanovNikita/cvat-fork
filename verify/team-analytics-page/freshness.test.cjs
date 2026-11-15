// How fresh the figures are: the time of the last successful refresh, and a warning once it is
// more than thirty minutes old (the service decides by its own clock).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

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

test('the page reads the status of the selected organization once the figures are shown', async () => {
    const { request, requests } = suppliedService((url) => (url.includes('/status') ?
        { body: { refresh: refresh({ stale: true, now: '2026-11-13T16:00:00+00:00' }) } } :
        { body: { by_annotator: { rows: [] } } }));
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const status = requests.find((request) => request.url.includes('/status'));
    assert.ok(status, 'status is requested');
    const url = new URL(status.url, 'http://localhost');
    assert.equal(url.pathname, '/api/team-analytics/status');
    // cvat-core attaches the organization; the page names none of its own
    assert.deepEqual(status.params, { tz: url.searchParams.get('tz') });
    assert.ok(view.container.querySelector('.cvat-team-analytics-stale'));
    await view.unmount();
});

// Mounts the page with the status read again every minute on a mocked clock; `answers` are the
// successive status answers (an Error is a failed read), the last one repeating.
async function openWithClock(t, answers) {
    t.mock.timers.enable({ apis: ['setInterval', 'Date'], now: Date.parse('2026-11-13T15:30:00Z') });
    let reads = 0;
    const { request } = suppliedService((url) => {
        if (!url.includes('/status')) return { body: { by_annotator: { rows: [] } } };
        const answer = answers[Math.min(reads, answers.length - 1)];
        reads += 1;
        return answer instanceof Error ? answer : { body: { refresh: answer } };
    });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request, viewerTimeZone: () => 'UTC' },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const minutes = async (count) => {
        for (let i = 0; i < count; i += 1) {
            // eslint-disable-next-line no-await-in-loop
            await act(async () => { t.mock.timers.tick(60000); });
            // eslint-disable-next-line no-await-in-loop
            await view.settle();
        }
    };
    const shown = () => view.container.textContent;
    const warned = () => !!view.container.querySelector('.cvat-team-analytics-stale');
    return {
        view, minutes, shown, warned, reads: () => reads,
    };
}

test('an open page starts warning when the status read every minute says the figures are stale', async (t) => {
    const page = await openWithClock(t, [
        refresh(),
        refresh({ now: '2026-11-13T15:51:00+00:00', stale: true }),
    ]);
    try {
        assert.equal(page.warned(), false);
        await page.minutes(1);
        assert.equal(page.reads(), 2);
        assert.equal(page.warned(), true);
        assert.match(page.shown(), /last refreshed at 15:20, more than 30 minutes ago/);
    } finally {
        await page.view.unmount();
    }
});

test('when the status cannot be read the last time stays and the warning comes once it is too old', async (t) => {
    // fresh at 15:30 (last refresh 15:20); afterwards every read fails
    const page = await openWithClock(t, [refresh(), new Error('network down')]);
    try {
        await page.minutes(1);
        assert.match(page.shown(), /Data as of 15:20/);
        assert.equal(page.warned(), false);
        await page.minutes(20); // 15:51: the refresh is now 31 minutes old by the page's own clock
        assert.match(page.shown(), /Data as of 15:20/);
        assert.equal(page.warned(), true);
    } finally {
        await page.view.unmount();
    }
});

test('a refused caller is not asked about freshness', async () => {
    const { request, requests } = suppliedService(() => ({ status: 403, body: { error: 'forbidden' } }));
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    assert.equal(requests.filter((request) => request.url.includes('/status')).length, 0);
    await view.unmount();
});
