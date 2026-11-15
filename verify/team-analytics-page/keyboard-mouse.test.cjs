// Keyboard and mouse: hotkey actions, mouse actions, hotkey share, the most used hotkeys labelled from
// the viewer's own keymap, and the hotkey / mouse split of operations, from the `input` and
// `operations` sections the service sends.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const HOUR = 3600000;

const INPUT = {
    hotkey_actions: 1234567,
    mouse_actions: 411522,
    canvas_clicks: 90000,
    hotkey_share: 0.75,
    top_hotkeys: [
        { action: 'NEXT_FRAME', actions: 500000 },
        { action: 'SWITCH_DRAW_MODE_STANDARD_CONTROLS', actions: 300000 },
        { action: 'PREV_FRAME', actions: 200000 },
        { action: 'SWITCH_LABEL_1', actions: 100000 },
        { action: 'SAVE_JOB', actions: 60000 },
        { action: 'DELETE_OBJECT_STANDARD_WORKSPACE', actions: 40000 },
        { action: 'GONE_IN_A_NEWER_UI', actions: 20000 },
    ],
    rest: { count: 5, actions: 14567 },
};

// the viewer's keymap: action -> what it does and the keys it is bound to now
const LABELS = {
    NEXT_FRAME: { name: 'Next frame', keys: 'F' },
    SWITCH_DRAW_MODE_STANDARD_CONTROLS: { name: 'Draw mode', keys: 'N' },
    PREV_FRAME: { name: 'Previous frame', keys: 'D' },
    SWITCH_LABEL_1: { name: 'Switch label', keys: 'Ctrl+1' },
    SAVE_JOB: { name: 'Save the job', keys: 'Ctrl+S' },
    DELETE_OBJECT_STANDARD_WORKSPACE: { name: 'Delete object', keys: 'Del, Shift+Del' },
};

function opRow(operation, objects, hotkey, mouse) {
    return {
        operation, objects, timed_objects: objects, time_ms: HOUR, average_ms: 1000, share: 0.2,
        hotkey_objects: hotkey, mouse_objects: mouse,
    };
}

const OPERATIONS = {
    legacy: false,
    shapes: 'bounding_boxes',
    working_time_ms: 5 * HOUR,
    active_time_ms: 5 * HOUR,
    rows: [
        opRow('creation', 100, 30, 70),
        opRow('alignment', 50, 0, 50),
        opRow('class_change', 10, 9, 1),
        opRow('deletion', 4, 0, 0),
        { ...opRow('other', 0, 0, 0), time_ms: HOUR },
    ],
};

function ready(overview, props = {}) {
    return {
        organization: 'team-org',
        state: { kind: 'ready', overview: { by_annotator: { rows: [] }, operations: OPERATIONS, ...overview } },
        hotkeyLabels: LABELS,
        ...props,
    };
}

function card(html) {
    const match = html.match(/<section[^>]*cvat-team-analytics-keyboard[^>]*>(.*?)<\/section>/);
    assert.ok(match, 'the keyboard and mouse card is shown');
    return match[1];
}

test('the card shows hotkey actions, mouse actions and the hotkey share for the scope', () => {
    const html = card(render(View, ready({ input: INPUT })));
    const figures = text(html);
    assert.match(figures, /Hotkey actions 1\.23M/);
    assert.match(figures, /Mouse actions 412K/);
    assert.match(figures, /Hotkey share 75%/);
    assert.match(html, /title="1,234,567 exactly"/);
    assert.match(html, /title="1,234,567 hotkey actions of 1,646,089"/);
});

test('the seven most used hotkeys are named by action with the viewer\'s keys, the rest on one line', () => {
    const html = card(render(View, ready({ input: INPUT })));
    const rows = [...html.matchAll(/<li[^>]*cvat-team-analytics-hotkey-row[^>]*>(.*?)<\/li>/g)].map((m) => text(m[1]));
    assert.deepEqual(rows, [
        'Next frame F 500,000',
        'Draw mode N 300,000',
        'Previous frame D 200,000',
        'Switch label Ctrl+1 100,000',
        'Save the job Ctrl+S 60,000',
        'Delete object Del, Shift+Del 40,000',
        // an action the viewer's keymap does not know is shown by its name
        'GONE_IN_A_NEWER_UI — 20,000',
    ]);
    assert.match(text(html), /5 other hotkeys, not shown 14,567/);
});

test('a period without recorded input has no share and no hotkeys yet', () => {
    const figures = text(card(render(View, ready({
        input: {
            hotkey_actions: 0, mouse_actions: 0, canvas_clicks: 0, hotkey_share: null, top_hotkeys: [],
            rest: { count: 0, actions: 0 },
        },
    }))));
    assert.match(figures, /Hotkey share —/);
    assert.match(figures, /No hotkey actions in this period/);
    assert.doesNotMatch(figures, /other hotkeys/);
});

test('a legacy period says hotkey use was not recorded', () => {
    const html = render(View, ready({
        operations: { ...OPERATIONS, legacy: true, shapes: 'all' },
        input: {
            hotkey_actions: 0, mouse_actions: 0, canvas_clicks: 0, hotkey_share: null, top_hotkeys: [],
            rest: { count: 0, actions: 0 },
        },
    }));
    const figures = text(card(html));
    assert.match(figures, /Hotkey use was not recorded in this period/);
    assert.doesNotMatch(figures, /Hotkey actions 0/);
});

test('a scope without shape-tagged operations but with counted input shows its figures', () => {
    const figures = text(card(render(View, ready({
        operations: { ...OPERATIONS, legacy: true, shapes: 'all' },
        input: INPUT,
    }))));
    assert.match(figures, /Hotkey actions 1\.23M/);
    assert.doesNotMatch(figures, /not recorded/);
});

test('the operations table splits creation, class change and deletion into hotkey and mouse starts', () => {
    const html = render(View, ready({ input: INPUT }));
    const table = html.match(/<section[^>]*cvat-team-analytics-operations[^>]*>(.*?)<\/section>/)[1];
    assert.match(text(table), /Started by hotkey \/ mouse/);
    const cells = [...table.matchAll(/<td[^>]*cvat-team-analytics-input-split[^>]*>(.*?)<\/td>/g)].map((m) => text(m[1]));
    assert.deepEqual(cells, ['30% / 70%', 'Mouse only', '90% / 10%', '—']);
    assert.match(table, /title="Creation: 30% by hotkey, 70% by mouse"/);
});

test('in a legacy period the split is not recorded, alignment still mouse only', () => {
    const html = render(View, ready({ operations: { ...OPERATIONS, legacy: true, shapes: 'all' } }));
    const table = html.match(/<section[^>]*cvat-team-analytics-operations[^>]*>(.*?)<\/section>/)[1];
    const cells = [...table.matchAll(/<td[^>]*cvat-team-analytics-input-split[^>]*>(.*?)<\/td>/g)].map((m) => text(m[1]));
    assert.deepEqual(cells, ['Not recorded', 'Mouse only', 'Not recorded', 'Not recorded']);
});

test('the mounted page labels hotkeys from the viewer\'s keymap in the store', async () => {
    const answer = { body: { by_annotator: { rows: [] }, operations: OPERATIONS, input: INPUT } };
    const { request } = suppliedService((url) => (url.includes('/status') ? { body: {} } : answer));
    const store = {
        organizations: { current: { slug: 'team-org' } },
        shortcuts: {
            // the viewer remapped Next frame to G; Previous frame keeps several keys
            keyMap: {
                NEXT_FRAME: { name: 'Next frame', sequences: ['g'] },
                PREV_FRAME: { name: 'Previous frame', sequences: ['d', 'shift+d'] },
            },
            normalizedKeyMap: { NEXT_FRAME: '[G]', PREV_FRAME: '[D, Shift+D]' },
        },
    };
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select(store) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        const rows = text(card(view.container.innerHTML));
        assert.match(rows, /Next frame G 500,000/);
        assert.match(rows, /Previous frame D, Shift\+D 200,000/);
    } finally {
        await view.unmount();
    }
});
