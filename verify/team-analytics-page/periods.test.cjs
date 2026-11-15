// Choosing the period: the control, the page address and the browser's Back button, and the
// previous figures while new ones load (the page mounted in jsdom with a real memory history).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const { createMemoryHistory } = dependency('history');

const HOUR = 3600000;
const pad = (n) => String(n).padStart(2, '0');
// The viewer's current and previous month, worked out independently of the page.
const today = new Date();
const CURRENT = `${today.getFullYear()}-${pad(today.getMonth() + 1)}`;
const PREVIOUS = today.getMonth() === 0 ? `${today.getFullYear() - 1}-12` : `${today.getFullYear()}-${pad(today.getMonth())}`;
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];
const label = (month) => `${MONTH_NAMES[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}`;

function overviewFor(url) {
    const query = new URL(url, 'http://localhost').searchParams;
    const period = query.get('period');
    const ms = { week: 1, two_weeks: 2, month: 3, year: 4 }[period] * HOUR;
    return {
        period: {
            name: period, first_day: '2026-11-07', last_day: '2026-11-13', month: query.get('month'), to_date: false, unit: 'day',
        },
        by_annotator: { rows: [{ user_id: 11, user_name: `alice-${period}${query.get('month') ? `-${query.get('month')}` : ''}`, working_time_ms: ms }] },
    };
}

// Answers overview requests through `respond` (default: at once) and status requests at once.
async function openPage({ address = '/team-analytics', respond } = {}) {
    const { request, requests } = suppliedService((url) => {
        if (url.includes('/status')) return { body: { refresh: null } };
        return respond ? respond(url) : { body: overviewFor(url) };
    });
    const history = createMemoryHistory({ initialEntries: [address] });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const overviews = () => requests.filter((r) => r.url.includes('/overview'))
        .map((r) => Object.fromEntries(new URL(r.url, 'http://localhost').searchParams));
    const button = (name) => [...view.container.querySelectorAll('button')]
        .find((b) => b.textContent === name || b.getAttribute('aria-label') === name);
    const click = async (name) => {
        const target = button(name);
        assert.ok(target, `button ${name}`);
        await act(async () => { target.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
        await view.settle();
    };
    const go = async (move) => { await act(async () => { move(history); }); await view.settle(); };
    return {
        view, history, overviews, button, click, go, text: () => view.container.textContent.replace(/\s+/g, ' '),
    };
}

test('the period control offers Week, Two weeks, Month and Year, and no custom range', () => {
    const View = loadPage('team-analytics-view.tsx').default;
    const html = render(View, {
        organization: 'team-org',
        state: { kind: 'ready', overview: { by_annotator: { rows: [] } } },
        address: { period: 'week', month: null },
        currentMonth: '2026-11',
        onAddressChange() {},
    });
    const periods = html.match(/<div class="cvat-team-analytics-periods"[^>]*>(.*?)<\/div>/s);
    assert.ok(periods);
    const labels = [...periods[1].matchAll(/<button[^>]*>(.*?)<\/button>/g)].map((m) => text(m[1]));
    assert.deepEqual(labels, ['Week', 'Two weeks', 'Month', 'Year']);
    assert.match(periods[1], /aria-pressed="true"[^>]*>Week</);
    assert.doesNotMatch(html, /type="date"|Custom/);
});

test('the page opens on Week and asks the service for it', async () => {
    const page = await openPage();
    assert.deepEqual(page.overviews().map((q) => [q.period, q.month]), [['week', undefined]]);
    assert.match(page.text(), /Last 7 days/);
    await page.view.unmount();
});

test('a chosen period goes into the address and Back returns to the previous selection', async () => {
    const page = await openPage();
    await page.click('Two weeks');
    assert.equal(new URLSearchParams(page.history.location.search).get('period'), 'two_weeks');
    assert.match(page.text(), /alice-two_weeks/);
    assert.match(page.text(), /Last 14 days/);

    await page.click('Year');
    assert.equal(new URLSearchParams(page.history.location.search).get('period'), 'year');
    assert.match(page.text(), /Last 12 months/);

    await page.go((history) => history.goBack());
    assert.equal(new URLSearchParams(page.history.location.search).get('period'), 'two_weeks');
    assert.match(page.text(), /alice-two_weeks/);
    await page.go((history) => history.goBack());
    assert.match(page.text(), /alice-week/);
    assert.deepEqual(page.overviews().map((q) => q.period), ['week', 'two_weeks', 'year', 'two_weeks', 'week']);
    await page.view.unmount();
});

test('Month opens on the current month, to date, and later months cannot be chosen', async () => {
    const page = await openPage();
    await page.click('Month');
    const address = new URLSearchParams(page.history.location.search);
    assert.deepEqual([address.get('period'), address.get('month')], ['month', CURRENT]);
    assert.match(page.text(), new RegExp(`${label(CURRENT)} · to date`));
    assert.equal(page.button('Next month').disabled, true);
    assert.deepEqual(page.overviews().at(-1), {
        period: 'month', tz: page.overviews()[0].tz, month: CURRENT, shapes: 'bounding_boxes',
    });
    await page.view.unmount();
});

test('the team lead steps to earlier months and back, each month in the address', async () => {
    const page = await openPage({ address: '/team-analytics?period=month' });
    await page.click('Previous month');
    assert.equal(new URLSearchParams(page.history.location.search).get('month'), PREVIOUS);
    assert.match(page.text(), new RegExp(label(PREVIOUS)));
    assert.doesNotMatch(page.text(), /to date/);
    assert.equal(page.button('Next month').disabled, false);
    assert.equal(page.overviews().at(-1).month, PREVIOUS);

    await page.click('Next month');
    assert.equal(new URLSearchParams(page.history.location.search).get('month'), CURRENT);
    assert.match(page.text(), /to date/);

    await page.go((history) => history.goBack());
    assert.equal(page.overviews().at(-1).month, PREVIOUS);
    await page.view.unmount();
});

test('an address with a month opens that month; a later month or an unknown period falls back', async () => {
    let page = await openPage({ address: `/team-analytics?period=month&month=${PREVIOUS}` });
    assert.equal(page.overviews()[0].month, PREVIOUS);
    await page.view.unmount();

    page = await openPage({ address: '/team-analytics?period=month&month=2999-01' });
    assert.equal(page.overviews()[0].month, CURRENT);
    await page.view.unmount();

    page = await openPage({ address: '/team-analytics?period=custom&month=2026-01' });
    assert.deepEqual([page.overviews()[0].period, page.overviews()[0].month], ['week', undefined]);
    await page.view.unmount();
});

test('choosing the period already shown adds no history entry, so Back still leaves it', async () => {
    const page = await openPage();
    try {
        const entries = page.history.length;
        await page.click('Week');
        assert.equal(page.history.length, entries);
        assert.equal(page.history.location.search, '');
        assert.equal(page.overviews().length, 1);
    } finally {
        await page.view.unmount();
    }
});

test('changing the period keeps other parts of the address', async () => {
    const page = await openPage({ address: '/team-analytics?project=4&org=team-org&view=annotators' });
    await page.click('Month');
    await page.click('Week');
    const address = new URLSearchParams(page.history.location.search);
    assert.equal(address.get('project'), '4');
    assert.equal(address.get('view'), 'annotators');
    assert.equal(address.get('month'), null);
    await page.view.unmount();
});

test('while figures for a new period load, the previous ones stay on screen dimmed', async () => {
    let release;
    const page = await openPage({
        respond: (url) => (url.includes('period=year') ?
            new Promise((resolve) => { release = () => resolve({ body: overviewFor(url) }); }) :
            { body: overviewFor(url) }),
    });
    try {
        await page.click('Year');
        assert.match(page.text(), /alice-week/, 'the previous figures stay');
        const header = () => page.view.container
            .querySelector('.cvat-team-analytics-working-time-by-annotator .cvat-team-analytics-card-header')
            .textContent;
        assert.match(header(), /Last 7 days/, 'still named for the period they cover');
        const cards = page.view.container.querySelector('.cvat-team-analytics-cards');
        assert.ok(cards.classList.contains('cvat-team-analytics-pending'), 'and are dimmed');
        assert.equal(cards.getAttribute('aria-busy'), 'true');
        assert.equal(page.view.container.querySelector('.cvat-team-analytics-loading'), null);

        await act(async () => { release(); });
        await page.view.settle();
        assert.match(page.text(), /alice-year/);
        assert.match(header(), /Last 12 months/);
        assert.ok(!page.view.container.querySelector('.cvat-team-analytics-cards')
            .classList.contains('cvat-team-analytics-pending'));
    } finally {
        if (release) await act(async () => { release(); });
        await page.view.unmount();
    }
});
