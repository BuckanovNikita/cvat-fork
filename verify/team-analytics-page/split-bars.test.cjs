// The overview's working time by annotator and by project: each bar split by operation in the full view's
// colours, with a legend, and the row's working time still shown.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, render, text } = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const MINUTE = 60000;
const HOUR = 60 * MINUTE;

// the operation parts of a row, in the shape of a full-view row's `operations`
function parts(creation, alignment, classChange, deletion, other) {
    const figures = (time) => ({
        objects: time > 0 ? 1 : 0, timed_objects: time > 0 ? 1 : 0, time_ms: time, average_ms: time > 0 ? time : null,
    });
    return {
        creation: figures(creation),
        alignment: figures(alignment),
        class_change: figures(classChange),
        deletion: figures(deletion),
        other: { time_ms: other },
    };
}

function overview(legacy = false) {
    return {
        by_annotator: {
            legacy,
            rows: [
                {
                    user_id: 11, user_name: 'alice', working_time_ms: 2 * HOUR,
                    operations: parts(60 * MINUTE, 30 * MINUTE, legacy ? 0 : 10 * MINUTE, 5 * MINUTE, 15 * MINUTE),
                },
                { user_id: 12, user_name: 'bob', working_time_ms: HOUR, operations: parts(HOUR, 0, 0, 0, 0) },
            ],
            rest: { count: 0, working_time_ms: 0, operations: parts(0, 0, 0, 0, 0) },
        },
        by_project: {
            legacy,
            rows: [{ project_id: 1, working_time_ms: 2 * HOUR, operations: parts(HOUR, 0, 0, 0, HOUR) }],
            rest: { count: 0, working_time_ms: 0, operations: parts(0, 0, 0, 0, 0) },
        },
        headline: { annotators: 2, projects: 1 },
        filters: { project: null, annotator: null },
    };
}

function card(html, kind) {
    const root = document.createElement('div');
    root.innerHTML = html;
    return root.querySelector(`.cvat-team-analytics-working-time-by-${kind}`);
}

// each bar's parts as [colour, size, hover text]
function bars(section, kind) {
    return [...section.querySelectorAll(`.cvat-team-analytics-${kind}-row`)].map((row) => (
        [...row.querySelectorAll('.cvat-team-analytics-bar-part')].map((part) => [
            part.style.background, Number(part.style.flexGrow), part.getAttribute('title'),
        ])));
}

function legend(section) {
    return [...section.querySelectorAll('.cvat-team-analytics-breakdown-legend-item')]
        .map((item) => text(item.outerHTML));
}

// the full view's colours (operations.ts), as the browser reports them
const CREATION = 'rgb(42, 120, 214)';
const ALIGNMENT = 'rgb(235, 104, 52)';
const CLASS_CHANGE = 'rgb(27, 175, 122)';
const DELETION = 'rgb(237, 161, 0)';
const OTHER = 'rgb(201, 200, 194)';

test('each annotator bar is drawn as its operations and Other, with a legend and the working time', () => {
    const section = card(render(View, { organization: 'team-org', state: { kind: 'ready', overview: overview() } }),
        'annotator');

    assert.deepEqual(legend(section), ['Creation', 'Alignment', 'Class change', 'Deletion', 'Other']);
    const [alice, bob] = bars(section, 'annotator');
    assert.deepEqual(alice, [
        [CREATION, 60 * MINUTE, 'alice · Creation: 1.0 h'],
        [ALIGNMENT, 30 * MINUTE, 'alice · Alignment: 0.5 h'],
        [CLASS_CHANGE, 10 * MINUTE, 'alice · Class change: 0.2 h'],
        [DELETION, 5 * MINUTE, 'alice · Deletion: 0.1 h'],
        [OTHER, 15 * MINUTE, 'alice · Other: 0.3 h'],
    ]);
    assert.deepEqual(bob.map(([colour, size]) => [colour, size]),
        [[CREATION, HOUR], [ALIGNMENT, 0], [CLASS_CHANGE, 0], [DELETION, 0], [OTHER, 0]]);
    // the row still reads as its working time, and the longest bar is the full width
    const rows = [...section.querySelectorAll('.cvat-team-analytics-annotator-row')].map((row) => text(row.outerHTML));
    assert.deepEqual(rows, ['alice 2.0 h', 'bob 1.0 h']);
    const widths = [...section.querySelectorAll('.cvat-team-analytics-bar-fill')].map((fill) => fill.style.width);
    assert.deepEqual(widths, ['100%', '50%']);
});

test('each project bar is split the same way', () => {
    const section = card(render(View, { organization: 'team-org', state: { kind: 'ready', overview: overview() } }),
        'project');

    assert.deepEqual(legend(section), ['Creation', 'Alignment', 'Class change', 'Deletion', 'Other']);
    assert.deepEqual(bars(section, 'project')[0].map(([colour, size]) => [colour, size]),
        [[CREATION, HOUR], [ALIGNMENT, 0], [CLASS_CHANGE, 0], [DELETION, 0], [OTHER, HOUR]]);
    assert.match(text(section.outerHTML), /Project #1 2\.0 h/);
});

test('in a legacy period class change is neither a part nor in the legend, as in the full view', () => {
    const html = render(View, { organization: 'team-org', state: { kind: 'ready', overview: overview(true) } });
    for (const kind of ['annotator', 'project']) {
        const section = card(html, kind);
        assert.deepEqual(legend(section), ['Creation', 'Alignment', 'Deletion', 'Other']);
        assert.deepEqual(bars(section, kind)[0].map(([colour]) => colour), [CREATION, ALIGNMENT, DELETION, OTHER]);
    }
});

// A row whose answer carries no operation parts (a page in front of an older service during an upgrade) is
// drawn whole in a colour the legend gives to no operation, so it never reads as one operation's time.
const LEGEND_COLOURS = [CREATION, ALIGNMENT, CLASS_CHANGE, DELETION, OTHER];

function withoutParts(answer, keep = () => false) {
    const strip = (section) => ({
        ...section,
        rows: section.rows.map((row) => {
            if (keep(row)) return row;
            const { operations, ...rest } = row;
            return rest;
        }),
    });
    return { ...answer, by_annotator: strip(answer.by_annotator), by_project: strip(answer.by_project) };
}

function assertUnsplit(bar, hover) {
    assert.equal(bar.length, 1, 'the bar is one part');
    const [[colour, , title]] = bar;
    assert.ok(colour, 'the bar has a colour');
    assert.ok(!LEGEND_COLOURS.includes(colour), `${colour} is a colour of the legend`);
    assert.equal(title, hover);
}

test('a row without operation parts is drawn in no colour of the legend', () => {
    const html = render(View, { organization: 'team-org', state: { kind: 'ready', overview: withoutParts(overview()) } });
    const [alice, bob] = bars(card(html, 'annotator'), 'annotator');
    assertUnsplit(alice, 'alice: 2.0 h, not split by operation');
    assertUnsplit(bob, 'bob: 1.0 h, not split by operation');
    assertUnsplit(bars(card(html, 'project'), 'project')[0], 'Project #1: 2.0 h, not split by operation');
});

test('beside rows with parts, a row without them is still drawn in no colour of the legend', () => {
    const answer = withoutParts(overview(), (row) => row.user_name === 'alice');
    const section = card(render(View, { organization: 'team-org', state: { kind: 'ready', overview: answer } }),
        'annotator');
    assert.deepEqual(legend(section), ['Creation', 'Alignment', 'Class change', 'Deletion', 'Other']);
    const [alice, bob] = bars(section, 'annotator');
    assert.deepEqual(alice.map(([colour]) => colour), LEGEND_COLOURS);
    assertUnsplit(bob, 'bob: 1.0 h, not split by operation');
});

test('in a legacy period a row without operation parts is drawn the same way', () => {
    const html = render(View, {
        organization: 'team-org', state: { kind: 'ready', overview: withoutParts(overview(true)) },
    });
    assertUnsplit(bars(card(html, 'annotator'), 'annotator')[0], 'alice: 2.0 h, not split by operation');
});
