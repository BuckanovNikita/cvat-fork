// Ticket 10: class change is the fourth operation in the operations table and in the split of working
// time, with its count, average time, total time and share; in a legacy period it is not recorded.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, render, text } = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const HOUR = 3600000;

function row(operation, objects, timeMs, averageMs, share) {
    return { operation, objects, timed_objects: objects, time_ms: timeMs, average_ms: averageMs, share };
}

// 8 h of working time: creation 2 h, alignment 1 h, 240 class changes in 0.8 h (12 s each), deletion
// 0.2 h, Other 4 h
function operations(fields = {}) {
    return {
        legacy: false,
        shapes: 'bounding_boxes',
        working_time_ms: 8 * HOUR,
        active_time_ms: 8 * HOUR,
        rows: [
            row('creation', 500, 2 * HOUR, 14400, 0.25),
            row('alignment', 300, 1 * HOUR, 12000, 0.125),
            row('class_change', 240, 0.8 * HOUR, 12000, 0.1),
            row('deletion', 40, 0.2 * HOUR, 18000, 0.025),
            row('other', 0, 4 * HOUR, null, 0.5),
        ],
        ...fields,
    };
}

function ready(figures) {
    return {
        organization: 'team-org',
        state: { kind: 'ready', overview: { by_annotator: { rows: [] }, operations: figures } },
    };
}

// the header row and each operation's row of figures (the hotkey / mouse rows below them left out)
function tableRows(html) {
    const card = html.match(/<section[^>]*cvat-team-analytics-operations[^>]*>(.*?)<\/section>/);
    assert.ok(card, 'the operations table is shown');
    return [...card[1].matchAll(/<tr([^>]*)>(.*?)<\/tr>/g)]
        .filter((tr) => !tr[1].includes('cvat-team-analytics-input-split-row'))
        .map((tr) => [...tr[2].matchAll(/<t[hd][^>]*>(.*?)<\/t[hd]>/g)].map((cell) => text(cell[1])));
}

// the text of the hotkey / mouse row under the operation named `name`
function splitRow(html, name) {
    const card = html.match(/<section[^>]*cvat-team-analytics-operations[^>]*>(.*?)<\/section>/);
    const rows = [...card[1].matchAll(/<tr([^>]*)>(.*?)<\/tr>/g)];
    const index = rows.findIndex((tr) => !tr[1].includes('cvat-team-analytics-input-split-row') &&
        text(tr[2]).startsWith(name));
    assert.ok(index >= 0 && rows[index + 1]?.[1].includes('cvat-team-analytics-input-split-row'),
        `${name} has a split row under it`);
    return text(rows[index + 1][2]);
}

function legend(html) {
    const card = html.match(/<section[^>]*cvat-team-analytics-split[^>]*>(.*?)<\/section>/);
    assert.ok(card, 'the split card is shown');
    return [...card[1].matchAll(/<li[^>]*>(.*?)<\/li>/g)].map((item) => text(item[1]));
}

test('class change is the fourth operation of the table, with count, average, total and share', () => {
    const rows = tableRows(render(View, ready(operations())));

    assert.deepEqual(rows.map((cells) => cells[0]), ['Operation', 'Creation', 'Alignment', 'Class change', 'Deletion']);
    assert.deepEqual(rows[3], ['Class change', '240', '12 s', '0.8 h', '10%']);
    // a class change starts nothing with a key or the mouse: its split row shows a dash
    assert.match(splitRow(render(View, ready(operations())), 'Class change'), /—$/);
});

test('class change takes its part of the split of working time', () => {
    const html = render(View, ready(operations()));

    assert.deepEqual(legend(html), [
        'Creation 2.0 h 25%',
        'Alignment 1.0 h 13%',
        'Class change 0.8 h 10%',
        'Deletion 0.2 h 3%',
        'Other 4.0 h 50%',
    ]);
    assert.match(html, /title="Class change: 0\.8 h \(10%\)"/);
});

test('in a legacy period class change reads as not recorded, not as zero', () => {
    const html = render(View, ready(operations({
        legacy: true,
        shapes: 'all',
        rows: operations().rows.map((r) => (r.operation === 'class_change' ? row('class_change', 0, 0, null, 0) : r)),
    })));

    assert.deepEqual(tableRows(html)[3], ['Class change', 'Not recorded', '—', '—', '—']);
    assert.match(splitRow(html, 'Class change'), /Not recorded$/);
    assert.ok(legend(html).every((item) => !item.startsWith('Class change')));
});
