// Processed history on the page: one progress bar while history is processed, periods offered only
// when all of them is processed, no figure for a period that is not, and trends held back until three
// complete weeks are ready.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;

const FIGURES = { by_annotator: { rows: [{ user_id: 11, user_name: 'alice-figures', working_time_ms: 3600000 }] } };

// An overview of a period not wholly processed, as the service sends it: the envelope, and every figure null.
const NO_FIGURES = {
    period: {
        from: '2026-11-09T00:00:00+00:00', to: '2026-11-13T16:00:00+00:00', name: 'week', tz: 'UTC',
        first_day: '2026-11-09', last_day: '2026-11-15', month: null, to_date: false, unit: 'day',
    },
    filters: { project: null, annotator: { user_id: 11, user_name: 'alice-echoed' } },
    processed: false,
    headline: null,
    sessions: null,
    by_annotator: null,
    by_project: null,
    time_series: null,
    input: null,
    creation_methods: null,
    saved_boxes: null,
    operations: {
        legacy: false, partly_legacy: true, cutover: '2026-11-10T08:00:00+00:00', shapes: 'bounding_boxes',
        working_time_ms: null, active_time_ms: null, rows: null,
    },
};

// The history block of the status (only administrators read it).
function history(overrides = {}) {
    return {
        complete: false,
        percent: 6,
        ready_from: '2026-11-02T00:00:00+00:00',
        ready_from_day: '2026-11-02',
        first_day: '2026-04-30',
        days_ready: 12,
        days_total: 198,
        periods: {
            week: true, two_weeks: false, month: false, year: false,
        },
        earliest_month: null,
        complete_weeks: 1,
        trends_ready: false,
        ...overrides,
    };
}

function view({ status = { history: history() }, overview = FIGURES, address = { period: 'week', month: null } } = {}) {
    return render(View, {
        organization: 'team-org',
        state: { kind: 'ready', overview },
        address,
        onAddressChange() {},
        currentMonth: '2026-11',
        status,
        timeZone: 'UTC',
    });
}

function buttons(html) {
    // [label or aria-label, disabled, title] of every button
    return [...html.matchAll(/<button([^>]*)>(.*?)<\/button>/g)].map(([, attributes, inner]) => ({
        name: (attributes.match(/aria-label="([^"]*)"/) || [])[1] || text(inner),
        disabled: /\sdisabled=""/.test(attributes),
        title: (attributes.match(/title="([^"]*)"/) || [])[1] || null,
    }));
}

test('an overview without figures shows only why, and the filter row still names the selected annotator', () => {
    const shown = text(view({ overview: NO_FIGURES, address: { period: 'week', month: null, annotator: 11 } }));
    assert.match(shown, /This period is not processed yet/);
    assert.match(shown, /alice-echoed/);
});

test('while history is processed one progress bar shows the earliest ready date and how far it is', () => {
    const html = view();
    const shown = text(html);
    assert.match(shown, /Processing history/);
    assert.match(shown, /Ready from Nov 2, 2026 · 12 of 198 days/);
    assert.match(shown, /6%/);
    assert.equal((html.match(/role="progressbar"/g) || []).length, 1);
    assert.match(html, /aria-valuenow="6"/);
    assert.match(shown, /Recent days are processed first\./);
});

// a status without the day counts (an older server): the bar still reads
function percentOnlyHistory(overrides = {}) {
    const block = history({ percent: 37, ...overrides });
    for (const key of ['ready_from', 'ready_from_day', 'first_day', 'days_ready', 'days_total']) delete block[key];
    return block;
}

test('without the day counts the progress bar reads as the percentage alone', () => {
    const html = view({ status: { history: percentOnlyHistory() } });
    const shown = text(html);
    assert.match(shown, /Processing history/);
    assert.match(shown, /37%/);
    assert.match(html, /aria-valuenow="37"/);
    assert.match(html, /width:\s*37%/);
    assert.doesNotMatch(shown, /of \d+ days|Ready from|Nothing ready yet|undefined|NaN/);
});

test('with the day counts the line shows them and the bar the percentage from the service', () => {
    const shown = text(view({ status: { history: history({ percent: 7 }) } }));
    assert.match(shown, /Ready from Nov 2, 2026 · 12 of 198 days/);
    assert.match(shown, /7%/);
});

test('without the day counts the periods are still offered only when processed', () => {
    const periods = buttons(view({ status: { history: percentOnlyHistory() } }))
        .filter((b) => ['Week', 'Two weeks', 'Month', 'Year'].includes(b.name));
    assert.deepEqual(periods.map((b) => [b.name, b.disabled]), [
        ['Week', false], ['Two weeks', true], ['Month', true], ['Year', true],
    ]);
});

test('no progress bar once history is complete, or when the status is not known', () => {
    for (const status of [{ history: history({ complete: true, ready_from: null, ready_from_day: null }) }, null, {}]) {
        const html = view({ status });
        assert.doesNotMatch(text(html), /Processing history/);
        assert.doesNotMatch(html, /role="progressbar"/);
    }
});

test('before anything is processed the bar says nothing is ready yet', () => {
    const shown = text(view({ status: { history: history({
        ready_from: null, ready_from_day: null, days_ready: 0, percent: 0,
    }) } }));
    assert.match(shown, /Nothing ready yet · 0 of 198 days/);
    assert.match(shown, /0%/);
});

test('periods not wholly processed are disabled with an explanation', () => {
    const periods = buttons(view()).filter((b) => ['Week', 'Two weeks', 'Month', 'Year'].includes(b.name));
    assert.deepEqual(periods.map((b) => [b.name, b.disabled, b.title]), [
        ['Week', false, null],
        ['Two weeks', true, 'Not processed yet'],
        ['Month', true, 'Not processed yet'],
        ['Year', true, 'Not processed yet'],
    ]);
});

test('every period is offered once history is complete, or when the status is not known', () => {
    for (const status of [{ history: history({ complete: true, periods: { week: true, two_weeks: true, month: true, year: true } }) }, null]) {
        assert.ok(buttons(view({ status })).every((b) => !b.disabled || b.name === 'Next month'));
    }
});

test('an earlier month is offered only when all of it is processed', () => {
    const month = { period: 'month', month: '2026-10' };
    const status = (overrides) => ({ history: history({ periods: { week: true, two_weeks: true, month: true, year: false }, ...overrides }) });
    const previous = (html) => buttons(html).find((b) => b.name === 'Previous month');
    assert.equal(previous(view({ address: month, status: status({ earliest_month: '2026-10' }) })).disabled, true);
    assert.equal(previous(view({ address: month, status: status({ earliest_month: '2026-10' }) })).title, 'Not processed yet');
    assert.equal(previous(view({ address: month, status: status({ earliest_month: '2026-09' }) })).disabled, false);
    assert.equal(previous(view({ address: month, status: status({ complete: true, earliest_month: null }) })).disabled, false);
});

test('a period that is not wholly processed shows no figure, only why', () => {
    const shown = text(view({ overview: NO_FIGURES }));
    assert.doesNotMatch(shown, /alice-figures|1\.0 h/);
    assert.match(shown, /This period is not processed yet/);

    assert.match(text(view({ overview: { ...FIGURES, processed: true } })), /alice-figures/);
    assert.match(text(view({ overview: FIGURES })), /alice-figures/); // a service that does not say
});

test('trends are replaced by a short notice until three complete weeks are ready', () => {
    const shown = text(view({ status: { history: history({ complete_weeks: 2 }) } }));
    assert.match(shown, /Trends appear as history is processed/);
    assert.match(shown, /A trend needs at least three complete weeks\. Two are ready so far\./);
    assert.match(text(view({ status: { history: history({ complete_weeks: 0 }) } })), /None are ready so far\./);
    assert.match(text(view({ status: { history: history({ complete_weeks: 1 }) } })), /One is ready so far\./);

    for (const status of [{ history: history({ complete_weeks: 3, trends_ready: true }) }, null]) {
        assert.doesNotMatch(text(view({ status })), /Trends appear as history is processed/);
    }
});

test('an open page shows the figures once its period has been processed meanwhile', async (t) => {
    t.mock.timers.enable({ apis: ['setInterval', 'Date'], now: Date.parse('2026-11-13T15:30:00Z') });
    let processed = false;
    const { request, requests } = suppliedService((url) => {
        if (url.includes('/status')) {
            return { body: { history: processed ? history({ complete: true }) : history({ periods: { week: false } }) } };
        }
        return { body: processed ? { ...FIGURES, processed } : NO_FIGURES };
    });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request, viewerTimeZone: () => 'UTC' },
    }).default;
    const view = await mount(React.createElement(Page));
    const overviews = () => requests.filter((request) => request.url.includes('/overview')).length;
    try {
        await view.settle();
        assert.match(view.container.textContent, /This period is not processed yet/);
        await act(async () => { t.mock.timers.tick(60000); }); // still not processed: no new request
        await view.settle();
        assert.equal(overviews(), 1);

        processed = true;
        await act(async () => { t.mock.timers.tick(60000); });
        await view.settle();
        assert.equal(overviews(), 2);
        assert.match(view.container.textContent, /alice-figures/);
        assert.doesNotMatch(view.container.textContent, /This period is not processed yet|Processing history/);
    } finally {
        await view.unmount();
    }
});

test('the page asks for the status in the viewer time zone and shows the bar beside the notice', async () => {
    const { request, requests } = suppliedService((url) => (url.includes('/status') ?
        { body: { history: history() } } :
        { body: NO_FIGURES }));
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request, viewerTimeZone: () => 'Asia/Tokyo' },
    }).default;
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        const status = requests.find((request) => request.url.includes('/status'));
        assert.ok(status, 'status is requested');
        assert.equal(new URL(status.url, 'http://localhost').searchParams.get('tz'), 'Asia/Tokyo');
        const shown = view.container.textContent;
        assert.match(shown, /Processing history/);
        assert.match(shown, /This period is not processed yet/);
        assert.doesNotMatch(shown, /alice-figures/);
    } finally {
        await view.unmount();
    }
});
