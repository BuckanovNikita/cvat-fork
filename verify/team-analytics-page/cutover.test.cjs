// The cutover to the new activity logging, as the page shows it: a period before it is legacy (its notice, no
// shape switch), one that holds it is partly legacy (a short notice naming the date, the switch stays), and one
// after it is neither, whatever its scope holds.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, render, text } = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const HOUR = 3600000;
const CUTOVER = '2026-11-02T10:00:00+00:00';

function operations({ legacy = false, partly = false } = {}) {
    const row = (operation, objects) => ({
        operation, objects, timed_objects: objects, time_ms: HOUR, average_ms: 1000, share: 0.2,
    });
    return {
        legacy,
        partly_legacy: partly,
        cutover: partly || !legacy ? CUTOVER : null,
        shapes: legacy ? 'all' : 'bounding_boxes',
        working_time_ms: 5 * HOUR,
        active_time_ms: 5 * HOUR,
        rows: [row('creation', 10), row('alignment', 4), row('class_change', 2), row('deletion', 1), row('other', 0)],
    };
}

function page(figures, timeZone = 'UTC') {
    return render(View, {
        organization: 'team-org',
        state: { kind: 'ready', overview: { by_annotator: { rows: [] }, operations: figures } },
        address: {
            period: 'month', month: '2026-11', project: null, annotator: null, shapes: 'bounding_boxes',
        },
        onAddressChange() {},
        timeZone,
    });
}

const LEGACY = /This period was recorded before the new activity logging/;
const PARTLY = /The new activity logging started on 2 November 2026/;
const SINCE = /Bounding box figures, class changes and hotkey use cover only the days since/;

test('a period that holds the cutover names the date, says what covers only the days since, and keeps the switch', () => {
    const html = page(operations({ partly: true }));
    assert.match(text(html), PARTLY);
    assert.match(text(html), SINCE);
    assert.doesNotMatch(text(html), LEGACY);
    assert.match(html, /aria-label="Shapes"/);
    assert.match(html, /cvat-team-analytics-partly-legacy-notice/);
});

test('the cutover date is the viewer\'s calendar day', () => {
    const late = { ...operations({ partly: true }), cutover: '2026-11-01T22:00:00+00:00' };
    assert.match(text(page(late, 'Europe/Moscow')), PARTLY);
    assert.match(text(page(late, 'UTC')), /started on 1 November 2026/);
});

test('a legacy period shows the legacy notice only, and no switch', () => {
    const html = page(operations({ legacy: true }));
    assert.match(text(html), LEGACY);
    assert.doesNotMatch(text(html), PARTLY);
    assert.doesNotMatch(html, /aria-label="Shapes"/);
});

test('a period after the cutover has neither notice', () => {
    const html = page(operations());
    assert.doesNotMatch(text(html), LEGACY);
    assert.doesNotMatch(text(html), /new activity logging started/);
    assert.match(html, /aria-label="Shapes"/);
});

test('an empty period that holds the cutover shows only the empty state, without either notice', () => {
    // as an older service answers it: partly legacy, although the scope has no job work in the period
    const empty = {
        ...operations({ partly: true }),
        working_time_ms: 0,
        active_time_ms: 0,
        rows: operations().rows.map((row) => ({
            ...row, objects: 0, timed_objects: 0, time_ms: 0, average_ms: null, share: null,
        })),
    };
    const html = page(empty);
    assert.match(text(html), /No job work in this period/);
    assert.doesNotMatch(text(html), LEGACY);
    assert.doesNotMatch(text(html), /new activity logging started/);
});
