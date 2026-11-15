// Creation methods: the card listing drawn, pasted and propagated with counts, shares and average times,
// and the per-method averages under the headline average, from the `creation_methods` section.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    loadPage, render, suppliedService, text,
} = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const service = loadPage('service.ts');
const HOUR = 3600000;

function operations(shapes, creationAverage = 3750) {
    return {
        legacy: false,
        shapes,
        working_time_ms: 10 * HOUR,
        active_time_ms: 10 * HOUR,
        rows: [
            {
                operation: 'creation', objects: 1200, timed_objects: 1000, time_ms: 1000 * creationAverage,
                average_ms: creationAverage, share: 0.1,
            },
            { operation: 'alignment', objects: 0, timed_objects: 0, time_ms: 0, average_ms: null, share: 0 },
            { operation: 'class_change', objects: 0, timed_objects: 0, time_ms: 0, average_ms: null, share: 0 },
            { operation: 'deletion', objects: 0, timed_objects: 0, time_ms: 0, average_ms: null, share: 0 },
            { operation: 'other', objects: 0, timed_objects: 0, time_ms: 9 * HOUR, average_ms: null, share: 0.9 },
        ],
    };
}

function method(name, objects, averageMs, share) {
    return {
        method: name, objects, timed_objects: objects, time_ms: objects * (averageMs ?? 0), average_ms: averageMs, share,
    };
}

function creationMethods(shapes) {
    return {
        shapes,
        rows: [
            method('drawn', 600, 6200, 0.5),
            method('pasted', 400, 1500, 1 / 3),
            method('propagated', 200, 800, 1 / 6),
        ],
        total: {
            objects: 1200, timed_objects: 1000, time_ms: 3750000, average_ms: 3750,
        },
    };
}

function ready(overview) {
    return { organization: 'team-org', state: { kind: 'ready', overview: { by_annotator: { rows: [] }, ...overview } } };
}

function card(html, className) {
    const match = html.match(new RegExp(`<section[^>]*${className}[^>]*>(.*?)</section>`));
    assert.ok(match, `${className} is shown`);
    return match[1];
}

function methodRows(html) {
    const body = card(html, 'cvat-team-analytics-creation-methods');
    return [...body.matchAll(/<tr[^>]*cvat-team-analytics-method-row[^>]*>(.*?)<\/tr>/g)].map((row) => row[1]);
}

const BOXES = ready({ operations: operations('bounding_boxes'), creation_methods: creationMethods('bounding_boxes') });
const ALL = ready({ operations: operations('all'), creation_methods: creationMethods('all') });

test('the card lists each method with its count, share and average time', () => {
    const rows = methodRows(render(View, BOXES)).map(text);
    assert.deepEqual(rows, [
        'Drawn 600 50% 6.2 s',
        'Pasted 400 33% 1.5 s',
        'Propagated 200 17% 0.8 s',
    ]);
});

test('every method has one bar, the longest for the largest count', () => {
    const widths = methodRows(render(View, BOXES)).map((row) => {
        const bars = [...row.matchAll(/class="cvat-team-analytics-method-bar"[^>]*style="[^"]*width:\s*([\d.]+)%/g)];
        assert.equal(bars.length, 1, 'one bar per method');
        return Math.round(Number(bars[0][1]) * 10) / 10;
    });
    assert.deepEqual(widths, [100, 66.7, 33.3]);
});

test('one line gives the three methods together, with the average the Creation operation uses', () => {
    const html = render(View, BOXES);
    const total = html.match(/<tr[^>]*cvat-team-analytics-methods-total[^>]*>(.*?)<\/tr>/);
    assert.ok(total, 'the total line is shown');
    assert.equal(text(total[1]), 'All annotator methods 1,200 3.8 s');
    assert.match(text(card(html, 'cvat-team-analytics-average-creation')), / 3\.8 s /);
});

test('the card is worded after the shapes the figures cover', () => {
    assert.ok(text(card(render(View, BOXES), 'cvat-team-analytics-creation-methods'))
        .startsWith('How boxes are created Each creation method counted on its own Method Boxes Share Avg time'));
    assert.ok(text(card(render(View, ALL), 'cvat-team-analytics-creation-methods'))
        .startsWith('How objects are created Each creation method counted on its own Method Objects Share Avg time'));
});

test('a method without a measured time or without creations shows no average or share', () => {
    const html = render(View, ready({
        operations: operations('all', null),
        creation_methods: {
            shapes: 'all',
            rows: [method('drawn', 0, null, null), method('pasted', 0, null, null), method('propagated', 0, null, null)],
            total: {
                objects: 0, timed_objects: 0, time_ms: 0, average_ms: null,
            },
        },
    }));
    assert.deepEqual(methodRows(html).map(text), ['Drawn 0 — —', 'Pasted 0 — —', 'Propagated 0 — —']);
});

test('the headline average time shows the per-method averages beneath it', () => {
    assert.equal(text(card(render(View, BOXES), 'cvat-team-analytics-average-creation')),
        'Avg time per box 3.8 s drawn 6.2 s · pasted 1.5 s · propagated 0.8 s');
});

test('without creation methods the headline keeps its plain line and no methods card is shown', () => {
    const html = render(View, ready({ operations: operations('all') }));
    assert.equal(text(card(html, 'cvat-team-analytics-average-creation')), 'Avg time per object 3.8 s to create one');
    assert.doesNotMatch(html, /cvat-team-analytics-creation-methods/);
});

test('creation methods reach the page from the overview response', async () => {
    const methods = creationMethods('all');
    const { request } = suppliedService(() => ({ body: { by_annotator: { rows: [] }, creation_methods: methods } }));
    const state = await service.loadOverview({ organization: 'team-org', timeZone: 'UTC' }, request);
    assert.equal(state.kind, 'ready');
    assert.deepEqual(state.overview.creation_methods, methods);
});
