// Trends and comparison: four charts over the last twelve weeks or months, one line for the scope or one
// per compared annotator or project, from the `trends` response the service sends.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const HOUR = 3600000;
const WEEKS = ['2026-08-24', '2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05',
    '2026-10-12', '2026-10-19', '2026-10-26', '2026-11-02', '2026-11-09'];
const COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];

function point(index, overrides = {}) {
    return {
        working_time_ms: (index + 1) * HOUR,
        legacy: false,
        boxes: 10 * (index + 1),
        timed_boxes: 10 * (index + 1),
        box_time_ms: 10 * (index + 1) * 4000,
        average_ms: 4000,
        hotkey_recorded: true,
        hotkey_actions: 3,
        mouse_actions: 1,
        hotkey_share: 0.75,
        ...overrides,
    };
}

function line(id, userName, change = () => ({})) {
    return { id, user_name: userName, points: WEEKS.map((_, index) => point(index, change(index))) };
}

function trends(overrides = {}) {
    return {
        step: 'week',
        tz: 'UTC',
        shapes: 'bounding_boxes',
        compare: 'annotators',
        buckets: WEEKS.map((start) => ({ start, processed: true })),
        lines: [line(null, null)],
        candidates: [
            { id: 11, user_name: 'alice', working_time_ms: 9 * HOUR },
            { id: 12, user_name: 'bob', working_time_ms: 8 * HOUR },
            { id: 13, user_name: 'carol', working_time_ms: 7 * HOUR },
            { id: 14, user_name: 'dave', working_time_ms: 6 * HOUR },
            { id: 15, user_name: 'erin', working_time_ms: 5 * HOUR },
            { id: 16, user_name: 'frank', working_time_ms: 4 * HOUR },
            { id: 17, user_name: 'grace', working_time_ms: 3 * HOUR },
        ],
        ...overrides,
    };
}

const Card = loadPage('cards/trends-card.tsx').default;

function card(props = {}) {
    return render(Card, {
        trends: trends(),
        step: 'week',
        kind: 'annotators',
        compared: [],
        query: '',
        scopeLabel: 'All annotators · All projects',
        ...props,
    });
}

function charts(html) {
    return [...html.matchAll(/<figure[^>]*cvat-team-analytics-trend-chart[^>]*>(.*?)<\/figure>/g)].map((m) => m[1]);
}

function legend(chart) {
    return [...chart.matchAll(/<li[^>]*cvat-team-analytics-trend-legend-item[^>]*>(.*?)<\/li>/g)].map((m) => text(m[1]));
}

function valueRows(chart) {
    return [...chart.matchAll(/<tr>(.*?)<\/tr>/g)].map((m) => [...m[1].matchAll(/<t[hd][^>]*>(.*?)<\/t[hd]>/g)]
        .map((cell) => text(cell[1])));
}

test('four charts: working time, boxes created, average time per box and hotkey share', () => {
    const html = card();
    const shown = text(html);
    assert.match(shown, /Trends Last 12 weeks, independent of the period above/);
    const titles = charts(html).map((chart) => text(chart.match(/cvat-team-analytics-trend-title[^>]*>(.*?)</)[1]));
    assert.deepEqual(titles, ['Working time', 'Boxes created', 'Average time per box', 'Hotkey share']);
});

test('with nothing compared each chart has one line for the scope, named in its legend', () => {
    for (const chart of charts(card())) {
        assert.equal([...chart.matchAll(/cvat-team-analytics-trend-line/g)].length, 1);
        assert.match(legend(chart)[0], /^All annotators · All projects /);
    }
    const [work, boxes, average, share] = charts(card()).map((chart) => legend(chart)[0]);
    // the legend gives the latest value, so no colour is needed to read it
    assert.match(work, /12\.0 h$/);
    assert.match(boxes, /120$/);
    assert.match(average, /4\.0 s$/);
    assert.match(share, /75%$/);
});

test('every value can be read as text: a table per chart and a title on every point', () => {
    const [work] = charts(card());
    const rows = valueRows(work);
    assert.deepEqual(rows[0], ['Week', 'All annotators · All projects']);
    assert.deepEqual(rows[1], ['Week of Aug 24', '1.0 h']);
    assert.deepEqual(rows[12], ['Week of Nov 9', '12.0 h']);
    assert.match(work, /title="All annotators · All projects · week of Nov 9: 12\.0 h"/);
});

test('each chart has one vertical scale of its own measure', () => {
    for (const chart of charts(card())) {
        assert.equal([...chart.matchAll(/cvat-team-analytics-trend-scale"/g)].length, 1);
    }
    const scales = charts(card()).map((chart) => text(chart.match(/cvat-team-analytics-trend-scale"[^>]*>(.*?)<\/div>/)[1]));
    assert.deepEqual(scales, ['20 h 10 h 0 h', '200 100 0', '5 s 2.5 s 0 s', '100% 50% 0%']);
});

test('all shapes name objects instead of boxes', () => {
    const titles = charts(card({ trends: trends({ shapes: 'all' }) }))
        .map((chart) => text(chart.match(/cvat-team-analytics-trend-title[^>]*>(.*?)</)[1]));
    assert.deepEqual(titles.slice(1, 3), ['Objects created', 'Average time per object']);
});

test('months are labelled by month', () => {
    const months = ['2025-12-01', '2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01', '2026-05-01', '2026-06-01',
        '2026-07-01', '2026-08-01', '2026-09-01', '2026-10-01', '2026-11-01'];
    const html = card({ step: 'month', trends: trends({ step: 'month', buckets: months.map((start) => ({ start, processed: true })) }) });
    assert.match(text(html), /Last 12 months/);
    const rows = valueRows(charts(html)[0]);
    assert.deepEqual(rows[0][0], 'Month');
    assert.deepEqual(rows[1][0], 'Dec 2025');
    assert.deepEqual(rows[12][0], 'Nov 2026');
});

test('weeks before the new logging show hotkey share as not recorded', () => {
    const old = (index) => (index < 4 ? {
        legacy: true, hotkey_recorded: false, hotkey_share: null, boxes: null, timed_boxes: null, box_time_ms: null,
        average_ms: null,
    } : {});
    const html = card({ trends: trends({ lines: [line(null, null, old)] }) });
    const [work, boxes, , share] = charts(html);
    assert.deepEqual(valueRows(share)[1], ['Week of Aug 24', 'Not recorded']);
    assert.deepEqual(valueRows(share)[5], ['Week of Sep 21', '75%']);
    assert.match(text(share), /Not recorded before the new logging/);
    // boxes of old weeks cannot be told apart either; working time is complete
    assert.deepEqual(valueRows(boxes)[1], ['Week of Aug 24', 'Not recorded']);
    assert.deepEqual(valueRows(work)[1], ['Week of Aug 24', '1.0 h']);
    // the line is broken where nothing was recorded, never drawn at zero
    assert.doesNotMatch(share, /title="[^"]*week of Aug 24/);
});

test('a chart with nothing recorded at all says so instead of drawing', () => {
    const none = () => ({ legacy: true, hotkey_recorded: false, hotkey_share: null });
    const [, , , share] = charts(card({ trends: trends({ lines: [line(null, null, none)] }) }));
    assert.doesNotMatch(share, /cvat-team-analytics-trend-line/);
    assert.match(text(share), /Not recorded before the new logging/);
});

// A point of a week not wholly processed, as the service sends it: the flags, and every value null.
const NO_FIGURES = {
    working_time_ms: null, boxes: null, timed_boxes: null, box_time_ms: null, average_ms: null,
    hotkey_actions: null, mouse_actions: null, hotkey_share: null,
};

test('weeks not processed yet are withheld', () => {
    const buckets = WEEKS.map((start, index) => ({ start, processed: index >= 9 }));
    const lines = [line(null, null, (index) => (index >= 9 ? {} : NO_FIGURES))];
    const html = card({ trends: trends({ buckets, lines }) });
    const [work, boxes, average, share] = charts(html);
    for (const chart of [boxes, average, share]) {
        assert.deepEqual(valueRows(chart)[1][1], 'Not processed yet');
    }
    assert.doesNotMatch(html, /NaN/);
    assert.deepEqual(valueRows(work)[1], ['Week of Aug 24', 'Not processed yet']);
    assert.deepEqual(valueRows(work)[10], ['Week of Oct 26', '10.0 h']);
    assert.doesNotMatch(work, /week of Aug 24:/);
});

test('compared annotators are one line each, named in the legend, coloured by their slot', () => {
    const html = card({
        trends: trends({ lines: [line(12, 'bob'), line(11, 'alice')] }),
        compared: [{ id: 12, slot: 3 }, { id: 11, slot: 0 }],
    });
    assert.match(text(html), /Comparing/);
    for (const chart of charts(html)) {
        assert.equal([...chart.matchAll(/cvat-team-analytics-trend-line/g)].length, 2);
        assert.deepEqual(legend(chart).map((item) => item.split(' ')[0]), ['bob', 'alice']);
        assert.match(chart, new RegExp(`stroke="${COLORS[3]}"`));
        assert.match(chart, new RegExp(`stroke="${COLORS[0]}"`));
    }
    const chips = [...html.matchAll(/<button[^>]*title="Remove ([^"]*)"/g)].map((m) => m[1]);
    assert.deepEqual(chips, ['bob', 'alice']);
});

test('compared projects are named as CVAT names them', () => {
    const html = card({
        kind: 'projects',
        trends: trends({ compare: 'projects', lines: [line(5, null), line(0, null)], candidates: [] }),
        compared: [{ id: 5, slot: 0 }, { id: 0, slot: 1 }],
        projectNames: { 5: 'Street scenes' },
    });
    assert.deepEqual(legend(charts(html)[0]).map((item) => item.replace(/ [\d.]+ h$/, '')), ['Street scenes', 'No project']);
});

test('people to compare are offered by typing, four at a time', () => {
    const offered = (html) => [...html.matchAll(/<button[^>]*cvat-team-analytics-compare-offer[^>]*>(.*?)<\/button>/g)]
        .map((m) => text(m[1]));
    let html = card();
    assert.match(html, /<input[^>]*type="search"[^>]*aria-label="Find an annotator"/);
    assert.deepEqual(offered(html), ['+ alice', '+ bob', '+ carol', '+ dave']);
    assert.match(text(html), /3 more match\. Type to narrow the list\./);
    html = card({ query: 'RA' });
    assert.deepEqual(offered(html), ['+ frank', '+ grace']);
    html = card({ query: 'zed' });
    assert.match(text(html), /No match/);
    assert.match(card({ kind: 'projects' }), /aria-label="Find a project"/);
});

test('at five compared, further choices are disabled with a hint', () => {
    const compared = [11, 12, 13, 14, 15].map((id, slot) => ({ id, slot }));
    const html = card({
        compared,
        trends: trends({ lines: compared.map(({ id }) => line(id, `user${id}`)) }),
    });
    assert.match(html, /<input[^>]*type="search"[^>]*disabled=""/);
    const offers = [...html.matchAll(/<button([^>]*cvat-team-analytics-compare-offer[^>]*)>/g)].map((m) => m[1]);
    assert.ok(offers.length > 0);
    for (const attributes of offers) {
        assert.match(attributes, /disabled=""/);
        assert.match(attributes, /title="Remove one to add another"/);
    }
    assert.match(text(html), /Up to 5 at once\. Remove one to add another\./);
});

test('a trends response that cannot be read says so', () => {
    assert.match(text(card({ trends: null, failed: true })), /Trends could not be loaded/);
    // a failed update keeps the previous charts, dimmed, and says so
    const html = card({ failed: true, pending: true });
    assert.match(text(html), /Trends could not be updated; the charts show the previous choice\./);
    assert.match(html, /cvat-team-analytics-trends cvat-team-analytics-pending/);
});

// --- the section: loading, comparing and the page around it -----------------------------------------------

function trendsAnswer(url) {
    const query = new URL(url, 'http://localhost').searchParams;
    const ids = (query.get('ids') || '').split(',').filter(Boolean).map(Number);
    const step = query.get('step') || 'week';
    const lines = ids.length ? ids.map((id) => line(id, `user${id}`)) : [line(null, null)];
    return { body: trends({ step, compare: query.get('compare'), lines }) };
}

function section(request, props = {}) {
    const Section = loadPage('trends-section.tsx', {
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    return React.createElement(Section, {
        organization: 'team-org', timeZone: 'UTC', project: null, annotator: null, shapes: 'bounding_boxes',
        scopeLabel: 'All annotators · All projects', ...props,
    });
}

async function click(element) {
    await act(async () => { element.click(); });
}

function swatches(container) {
    return Object.fromEntries([...container.querySelectorAll('button[title^="Remove "]')].map((button) => [
        button.title.slice('Remove '.length),
        button.querySelector('.cvat-team-analytics-compare-swatch').style.background,
    ]));
}

function offer(container, name) {
    return [...container.querySelectorAll('.cvat-team-analytics-compare-offer')].find((b) => b.textContent === `+ ${name}`);
}

const rgb = (hex) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`;

test('a compared line keeps its colour while others are added and removed', async () => {
    const { request, requests } = suppliedService(trendsAnswer);
    const page = await mount(section(request));
    try {
        await page.settle();
        for (const name of ['alice', 'bob', 'carol']) {
            // eslint-disable-next-line no-await-in-loop
            await click(offer(page.container, name));
            // eslint-disable-next-line no-await-in-loop
            await page.settle();
        }
        assert.deepEqual(swatches(page.container), { alice: rgb(COLORS[0]), bob: rgb(COLORS[1]), carol: rgb(COLORS[2]) });
        await click(page.container.querySelector('button[title="Remove alice"]'));
        await page.settle();
        await click(offer(page.container, 'dave'));
        await page.settle();
        // bob and carol keep theirs; dave takes the colour alice left
        assert.deepEqual(swatches(page.container), { bob: rgb(COLORS[1]), carol: rgb(COLORS[2]), dave: rgb(COLORS[0]) });
        const last = new URL(requests[requests.length - 1].url, 'http://localhost').searchParams;
        assert.equal(last.get('compare'), 'annotators');
        assert.equal(last.get('ids'), '12,13,14');
        // the chart lines carry the same colours
        const strokes = [...page.container.querySelector('.cvat-team-analytics-trend-chart').querySelectorAll('.cvat-team-analytics-trend-line')]
            .map((line) => line.getAttribute('stroke'));
        assert.deepEqual(strokes, [COLORS[1], COLORS[2], COLORS[0]]);
    } finally {
        await page.unmount();
    }
});

test('typing narrows the offer; switching to projects or months asks the service again', async () => {
    const { request, requests } = suppliedService(trendsAnswer);
    const page = await mount(section(request));
    try {
        await page.settle();
        const input = page.container.querySelector('input[type="search"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'gra');
            input.dispatchEvent(new window.Event('input', { bubbles: true }));
        });
        assert.deepEqual([...page.container.querySelectorAll('.cvat-team-analytics-compare-offer')].map((b) => b.textContent),
            ['+ grace']);
        await click([...page.container.querySelectorAll('[aria-label="Trend step"] button')]
            .find((b) => b.textContent === 'Months'));
        await page.settle();
        let last = new URL(requests[requests.length - 1].url, 'http://localhost').searchParams;
        assert.equal(last.get('step'), 'month');
        await click([...page.container.querySelectorAll('[aria-label="Compare"] button')]
            .find((b) => b.textContent === 'Projects'));
        await page.settle();
        last = new URL(requests[requests.length - 1].url, 'http://localhost').searchParams;
        assert.equal(last.get('compare'), 'projects');
        assert.equal(page.container.querySelector('input[type="search"]').getAttribute('aria-label'), 'Find a project');
    } finally {
        await page.unmount();
    }
});

test('trends follow the filters and the shape switch but not the period', async () => {
    const { createMemoryHistory } = dependency('history');
    const history = createMemoryHistory({ initialEntries: ['/team-analytics'] });
    const { request, requests } = suppliedService((url) => {
        if (url.includes('/trends?')) return trendsAnswer(url);
        if (url.includes('/status?')) return { body: {} };
        return { body: { by_annotator: { rows: [] } } };
    });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } }, shortcuts: { keyMap: {}, normalizedKeyMap: {} } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    const trendRequests = () => requests.filter((r) => r.url.includes('/trends?'))
        .map((r) => new URL(r.url, 'http://localhost').searchParams);
    const page = await mount(React.createElement(Page));
    try {
        await page.settle();
        assert.equal(trendRequests().length, 1);
        assert.equal(trendRequests()[0].get('period'), null);
        await act(async () => { history.push('/team-analytics?period=year'); });
        await page.settle();
        assert.equal(trendRequests().length, 1, 'a period change does not ask for trends again');
        assert.ok(page.container.querySelector('.cvat-team-analytics-trends'));
        await act(async () => { history.push('/team-analytics?period=year&project=3&annotator=11&org=team-org&shapes=all'); });
        await page.settle();
        const last = trendRequests()[trendRequests().length - 1];
        assert.equal(last.get('project'), '3');
        assert.equal(last.get('annotator'), '11');
        assert.equal(last.get('shapes'), 'all');
        assert.equal(last.get('org'), null, 'cvat-core attaches the organization');
        // weeks follow the viewer's time zone
        assert.equal(last.get('tz'), Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
    } finally {
        await page.unmount();
    }
});

test('trends are asked for again as history is processed', async () => {
    const { request, requests } = suppliedService(trendsAnswer);
    let advance;
    const { type: Section, props } = section(request);
    function Holder() {
        const [progress, setProgress] = React.useState('false|2026-11-09T00:00:00+00:00');
        advance = setProgress;
        return React.createElement(Section, { ...props, historyProgress: progress });
    }
    const page = await mount(React.createElement(Holder));
    try {
        await page.settle();
        assert.equal(requests.length, 1);
        await act(async () => { advance('false|2026-11-02T00:00:00+00:00'); });
        await page.settle();
        assert.equal(requests.length, 2);
    } finally {
        await page.unmount();
    }
});
