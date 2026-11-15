// Model and saved boxes on the page (ticket 12): Model is a fourth creation method with a count and a share
// and no time, outside the annotators' total; the headline shows Model boxes beside the boxes created; the
// re-upload note sits next to the Model figure; a legacy period gives its saved boxes, all methods together.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    loadPage, render, suppliedService, text,
} = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const service = loadPage('service.ts');
const HOUR = 3600000;

function operations({ shapes = 'bounding_boxes', legacy = false } = {}) {
    return {
        legacy,
        shapes,
        working_time_ms: 10 * HOUR,
        active_time_ms: 10 * HOUR,
        rows: [
            {
                operation: 'creation', objects: 1200, timed_objects: 1000, time_ms: 3750000, average_ms: 3750, share: 0.1,
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
        method: name, objects, timed_objects: objects, time_ms: objects * averageMs, average_ms: averageMs, share,
    };
}

// 1,200 by annotators and 800 by Model: shares of 2,000
function creationMethods({ shapes = 'bounding_boxes', model = 800, technical = 2 } = {}) {
    return {
        shapes,
        rows: [method('drawn', 600, 6200, 0.3), method('pasted', 400, 1500, 0.2), method('propagated', 200, 800, 0.1)],
        total: {
            objects: 1200, timed_objects: 1000, time_ms: 3750000, average_ms: 3750,
        },
        model: { objects: model, share: model / (1200 + model) },
        technical_accounts: technical,
    };
}

function savedBoxes(boxes = 1450) {
    return {
        boxes,
        by_annotator: [{ user_id: 11, user_name: 'alice', boxes: 650 }],
        by_project: [{ project_id: 1, boxes: boxes }],
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
    return [...body.matchAll(/<tr[^>]*cvat-team-analytics-method-row[^>]*>(.*?)<\/tr>/g)].map((row) => text(row[1]));
}

const CURRENT = ready({ operations: operations(), creation_methods: creationMethods(), saved_boxes: savedBoxes() });

test('Model is a fourth method with a count and a share and no time', () => {
    assert.deepEqual(methodRows(render(View, CURRENT)), [
        'Drawn 600 30% 6.2 s',
        'Pasted 400 20% 1.5 s',
        'Propagated 200 10% 0.8 s',
        'Model 800 40% —',
    ]);
});

test('Model is not part of the annotators\' total or its average', () => {
    const html = render(View, CURRENT);
    const total = html.match(/<tr[^>]*cvat-team-analytics-methods-total[^>]*>(.*?)<\/tr>/);
    assert.equal(text(total[1]), 'All annotator methods 1,200 3.8 s');
    assert.equal(text(card(html, 'cvat-team-analytics-average-creation')),
        'Avg time per box 3.8 s drawn 6.2 s · pasted 1.5 s · propagated 0.8 s');
});

test('the boxes created headline shows Model boxes beside the annotators\' figure, not inside it', () => {
    const tile = text(card(render(View, CURRENT), 'cvat-team-analytics-objects-created'));
    assert.equal(tile, 'Boxes created 1,200 by annotators · plus 800 by model');
});

test('next to the Model figure the card says what Model is and that a re-upload counts again', () => {
    const body = text(card(render(View, CURRENT), 'cvat-team-analytics-creation-methods'));
    assert.match(body, /Model 800 40% — .*Model: boxes saved by 2 technical accounts or made with the built-in detector\. A re-upload by a technical account counts again\./);
});

test('the note follows the number of technical accounts and the shapes shown', () => {
    const one = ready({ operations: operations({ shapes: 'all' }), creation_methods: creationMethods({ shapes: 'all', technical: 1 }) });
    assert.match(text(card(render(View, one), 'cvat-team-analytics-creation-methods')),
        /Model: objects saved by 1 technical account or made with the built-in detector\. A re-upload by a technical account counts again\./);
    const none = ready({ operations: operations(), creation_methods: creationMethods({ technical: 0 }) });
    const body = text(card(render(View, none), 'cvat-team-analytics-creation-methods'));
    assert.match(body, /Model: boxes made with the built-in detector\./);
    assert.doesNotMatch(body, /re-upload/);
});

test('a legacy period shows its saved boxes, labelled as all methods together', () => {
    const legacy = ready({
        operations: operations({ shapes: 'all', legacy: true }),
        creation_methods: creationMethods({ shapes: 'all', model: 0 }),
        saved_boxes: savedBoxes(1450),
    });
    assert.match(text(card(render(View, legacy), 'cvat-team-analytics-creation-methods')),
        /1,450 single-frame boxes were saved in this period, all methods together\./);
});

test('outside a legacy period saved boxes are not offered as the box figure', () => {
    assert.doesNotMatch(render(View, CURRENT), /all methods together/);
});

test('without Model figures the card and the headline stay as they were', () => {
    const methods = creationMethods();
    delete methods.model;
    delete methods.technical_accounts;
    const html = render(View, ready({ operations: operations(), creation_methods: methods }));
    assert.equal(methodRows(html).length, 3);
    assert.equal(text(card(html, 'cvat-team-analytics-objects-created')), 'Boxes created 1,200 by annotators');
});

test('Model and saved boxes reach the page from the overview response', async () => {
    const body = { by_annotator: { rows: [] }, creation_methods: creationMethods(), saved_boxes: savedBoxes() };
    const { request } = suppliedService(() => ({ body }));
    const state = await service.loadOverview({ organization: 'team-org', timeZone: 'UTC' }, request);
    assert.deepEqual(state.overview.creation_methods.model, body.creation_methods.model);
    assert.deepEqual(state.overview.saved_boxes, body.saved_boxes);
});
