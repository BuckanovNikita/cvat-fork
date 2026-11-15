// Ticket 13: hotkey actions, mouse actions and the input method of operations. Shortcuts go in through
// the UI's single shortcut dispatcher (utils/mousetrap-react.tsx, with Mousetrap supplied), clicks and
// key presses through the logging's window listeners (listenForInput, as cvat-app.tsx attaches them),
// and operations through their UI call sites; the batch the real cvat-core logger sends to the server
// comes out.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, annotationActions, canvasWrapper, coreLogger, dependency, domWindow, loadSource, objectState,
    openJob, uiBoundaries,
} = require('./helper.cjs');

const React = dependency('react');
const LOGGING = 'utils/team-analytics-logging';
const SUMMARY = 'team_analytics:input_summary';

const PAGE = `<!doctype html><html><body>
  <div class="cvat-annotation-header"><button id="save">Save</button><span id="header-text">job #13</span></div>
  <div class="cvat-canvas-controls-sidebar"><span id="draw-rectangle" class="anticon" role="img"></span></div>
  <div class="cvat-canvas-container"><svg id="canvas"><rect id="shape"></rect></svg></div>
  <div class="cvat-objects-sidebar"><button id="sidebar-delete" class="ant-btn">Delete</button>
    <div id="sidebar-empty"></div></div>
  <div class="ant-popover"><button id="popover-shape" class="ant-btn">Shape</button></div>
  <div class="cvat-canvas-context-menu"><span id="context-delete" class="anticon"></span></div>
  <div class="ant-modal-root"><div class="ant-modal"><button id="modal-ok" class="ant-btn">OK</button></div></div>
</body></html>`;

const KEY_MAP = {
    NEXT_FRAME: { name: 'Next frame', sequences: ['f'] },
    SWITCH_DRAW_MODE_STANDARD_CONTROLS: { name: 'Draw mode', sequences: ['n'] },
    DELETE_OBJECT_STANDARD_WORKSPACE: { name: 'Delete object', sequences: ['del', 'shift+del'] },
    UNDO: { name: 'Undo', sequences: ['ctrl+z'] },
};

/**
 * One annotation page: the logging module (shared by every UI source loaded here), the shortcut
 * dispatcher with `handlers`, a jsdom page with its zones, and an open 2D job.
 */
function annotationPage(handlers = {}, { job: jobOptions = {} } = {}) {
    const core = coreLogger();
    const job = openJob(core, jobOptions);
    const logging = loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
    const bound = {};
    const mousetrap = {
        bind(sequences, callback) { for (const sequence of [].concat(sequences)) bound[sequence] = callback; },
        unbind() {},
        prototype: {},
    };
    const { default: GlobalHotKeys } = loadSource('cvat-ui/src/utils/mousetrap-react.tsx', {
        mousetrap: { __esModule: true, default: mousetrap },
        react: { __esModule: true, ...React, default: React, useEffect: (effect) => { effect(); } },
        [LOGGING]: logging,
    });
    const keyMap = Object.fromEntries(Object.entries(KEY_MAP).map(([action, item]) => [
        action, { description: item.name, scope: 0, ...item },
    ]));
    const calls = [];
    const allHandlers = Object.fromEntries(Object.keys(KEY_MAP).map((action) => [action, (event, combo) => {
        calls.push(action);
        return handlers[action] ? handlers[action](event, combo) : undefined;
    }]));
    GlobalHotKeys({ keyMap, handlers: allHandlers });

    const window = domWindow(PAGE);
    // cvat-app.tsx: the logging's own window listeners, attached as the application attaches them
    logging.listenForInput(window);

    return {
        core,
        job,
        logging,
        window,
        calls,
        /** A key press: the keydown reaches the window, then Mousetrap runs the shortcut bound to `sequence`. */
        press(sequence, { repeat = false } = {}) {
            const event = new window.KeyboardEvent('keydown', { key: sequence, repeat, bubbles: true });
            window.document.body.dispatchEvent(event);
            bound[sequence](event, sequence);
        },
        click(id) {
            window.document.getElementById(id).dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
        },
        async summaries() {
            return (await core.sent()).filter((event) => event.obj_name === SUMMARY);
        },
    };
}

test('each use of a shortcut inside a job counts under its action name, whatever the key', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    page.logging.trackInputJob(page.job);
    page.press('del');
    page.press('shift+del'); // the same action under another key
    page.press('ctrl+z');
    page.logging.untrackInputJob();

    const [summary] = await page.summaries();
    assert.deepEqual(summary.payload.hotkeys, { DELETE_OBJECT_STANDARD_WORKSPACE: 2, UNDO: 1 });
    assert.deepEqual(page.calls, ['DELETE_OBJECT_STANDARD_WORKSPACE', 'DELETE_OBJECT_STANDARD_WORKSPACE', 'UNDO']);
});

// A held frame-navigation key counts the frames it moves: frame-navigation.test.cjs.
test('a held key counts once, and a frame-navigation key that moves no frame counts nothing', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    page.logging.trackInputJob(page.job);
    page.press('f'); // no frame change follows
    for (let i = 0; i < 9; i++) page.press('f', { repeat: true });
    page.press('ctrl+z');
    for (let i = 0; i < 9; i++) page.press('ctrl+z', { repeat: true });
    page.logging.untrackInputJob();

    const [summary] = await page.summaries();
    assert.deepEqual(summary.payload.hotkeys, { UNDO: 1 });
    // the shortcut itself still runs on every repeat
    assert.equal(page.calls.length, 20);
});

test('clicks on controls count per zone, canvas clicks apart, other clicks not at all', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    page.logging.trackInputJob(page.job);
    page.click('save');
    page.click('header-text');
    page.click('draw-rectangle');
    page.click('popover-shape');
    page.click('shape');
    page.click('canvas');
    page.click('sidebar-delete');
    page.click('sidebar-empty');
    page.click('modal-ok');
    page.click('context-delete'); // the canvas context menu renders outside the canvas
    page.logging.untrackInputJob();

    const [summary] = await page.summaries();
    assert.deepEqual(summary.payload.mouse, {
        header: 1, controls_sidebar: 1, popup: 2, canvas: 2, objects_sidebar: 1, modal: 1,
    });
    assert.deepEqual(summary.payload.hotkeys, {});
});

test('one summary at most once a minute, written only when the person acts, and at job close', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    page.logging.trackInputJob(page.job);
    page.press('ctrl+z');
    t.mock.timers.tick(30_000);
    page.press('ctrl+z');
    assert.deepEqual(await page.summaries(), [], 'less than a minute since the job opened');

    // five idle minutes: nothing is written
    t.mock.timers.tick(5 * 60_000);
    assert.deepEqual(await page.summaries(), []);

    page.click('save'); // the person is active again: one summary of what was counted before
    page.press('ctrl+z');
    page.click('save');
    const [first, ...others] = await page.summaries();
    assert.deepEqual(first.payload.hotkeys, { UNDO: 2 });
    assert.deepEqual(first.payload.mouse, {});
    assert.deepEqual(others, [], 'the next minute has not passed');
    assert.equal(first.scope, 'debug:info');
    assert.ok(ALLOWED_SCOPES.has(first.scope));
    assert.deepEqual([first.project_id, first.task_id, first.job_id], [11, 12, 13]);

    page.logging.untrackInputJob();
    const written = await page.summaries();
    assert.equal(written.length, 2);
    const last = written[1];
    assert.deepEqual(last.payload.hotkeys, { UNDO: 1 });
    assert.deepEqual(last.payload.mouse, { header: 2 });

    page.logging.untrackInputJob();
    page.press('ctrl+z');
    page.click('save');
    t.mock.timers.tick(5 * 60_000);
    page.click('save');
    assert.equal((await page.summaries()).length, 2, 'nothing outside a job, nothing twice at close');
});

test('a key press is a moment the person acts: a summary that is due is written then', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage();
    page.logging.trackInputJob(page.job);
    page.press('ctrl+z');
    t.mock.timers.tick(2 * 60_000);
    assert.deepEqual(await page.summaries(), []);

    // a key that is no shortcut (typing an attribute value): only the window listener sees it
    page.window.document.body.dispatchEvent(new page.window.KeyboardEvent('keydown', { key: 'a', bubbles: true }));
    const [summary, ...others] = await page.summaries();
    assert.deepEqual(summary.payload.hotkeys, { UNDO: 1 });
    assert.deepEqual(others, []);
});

test('no event per hotkey action: frame changes still compress into one event', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    let frame = 0;
    const page = annotationPage({
        // as annotation-actions.ts changeFrameAsync logs a frame change through the job logger
        NEXT_FRAME: () => {
            page.job.logger.log('change:frame', {
                from: frame, to: frame + 1, step: 1, count: 1,
            });
            frame += 1;
        },
    });
    page.logging.trackInputJob(page.job);
    page.press('f');
    for (let i = 0; i < 29; i++) page.press('f', { repeat: true });

    const events = await page.core.sent();
    assert.equal(events.length, 1, JSON.stringify(events));
    assert.equal(events[0].scope, 'change:frame');
    assert.equal(events[0].count, 30);
});

test('an action started by hotkey and finished with the mouse is a hotkey start', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage({
        // the canvas reports the start of drawing synchronously when drawing is enabled
        SWITCH_DRAW_MODE_STANDARD_CONTROLS: () => { wrapper.onCanvasDrawStart(); },
    });
    const job = { ...page.job, labels: [{ id: 1, name: 'car' }] };
    const { component: wrapper } = canvasWrapper(page.core, job, {}, { [LOGGING]: page.logging });
    page.logging.trackInputJob(job);

    page.press('n');
    page.click('canvas'); // the clicks that place the box
    page.click('canvas');
    wrapper.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'rectangle', points: [0, 0, 5, 5] }, duration: 900, continue: false },
    });

    const [drawn] = (await page.core.sent()).filter((event) => event.scope === 'draw:object');
    assert.equal(drawn.payload.input_method, 'hotkey');
});

test('a drawing started from a control is a mouse start, even when a key finishes it', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    const job = { ...page.job, labels: [{ id: 1, name: 'car' }] };
    const { component: wrapper } = canvasWrapper(page.core, job, {}, { [LOGGING]: page.logging });
    page.window.document.getElementById('popover-shape').addEventListener('click', () => wrapper.onCanvasDrawStart());
    page.logging.trackInputJob(job);

    page.press('f'); // an earlier shortcut
    page.click('popover-shape');
    page.click('canvas');
    page.press('n'); // finishes the polygon
    wrapper.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'polygon', points: [0, 0, 5, 5, 0, 5] }, duration: 900, continue: false },
    });
    // the next drawing starts by hotkey
    wrapper.onCanvasDrawStart();
    wrapper.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'rectangle', points: [0, 0, 5, 5] }, duration: 900, continue: false },
    });

    const drawn = (await page.core.sent()).filter((event) => event.scope === 'draw:object');
    assert.deepEqual(drawn.map((event) => event.payload.input_method), ['mouse', 'hotkey']);
});

test('a class change during a drawing leaves the drawing its own input method', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    const job = { ...page.job, labels: [{ id: 1, name: 'car' }, { id: 2, name: 'bus' }] };
    const { component: wrapper } = canvasWrapper(page.core, job, {}, { [LOGGING]: page.logging });
    page.window.document.getElementById('popover-shape').addEventListener('click', () => wrapper.onCanvasDrawStart());
    page.logging.trackInputJob(job);

    page.click('popover-shape'); // the drawing starts from a control
    page.click('canvas');
    // before finishing, a label hotkey changes the class of the activated object
    page.press('ctrl+z');
    page.logging.recordClassChange(job, [objectState({ clientID: 9, label: { id: 1 } })], { id: 2 }, 'hotkey');
    page.click('canvas');
    wrapper.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'rectangle', points: [0, 0, 5, 5] }, duration: 900, continue: false },
    });

    const sent = await page.core.sent();
    const [change] = sent.filter((event) => event.obj_name === 'team_analytics:class_change');
    assert.equal(change.payload.input_method, 'hotkey');
    const [drawn] = sent.filter((event) => event.scope === 'draw:object');
    assert.equal(drawn.payload.input_method, 'mouse');
});

test('a deletion confirmed in a dialog keeps the method that started it', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    page.job.actions = { get: async () => ({}) };
    const target = () => objectState({ clientID: 4, lock: true, delete: async () => true });
    const { actions, dispatch } = annotationActions(page.core, page.job, { states: [target()] }, {},
        { [LOGGING]: page.logging });
    const confirmed = [];
    page.window.document.getElementById('modal-ok').addEventListener('click', () => {
        confirmed.push(dispatch(actions.removeObjectAsync(target(), true)));
    });
    page.window.document.getElementById('sidebar-delete').addEventListener('click', () => {
        confirmed.push(dispatch(actions.removeObjectAsync(target(), true)));
    });
    page.logging.trackInputJob(page.job);

    page.press('del'); // a locked object: CVAT asks for confirmation
    page.click('modal-ok');
    await Promise.all(confirmed);
    page.click('sidebar-delete');
    await Promise.all(confirmed);
    page.press('ctrl+z');
    page.click('modal-ok');
    await Promise.all(confirmed);

    const deletions = (await page.core.sent()).filter((event) => event.scope === 'delete:object');
    assert.deepEqual(deletions.map((event) => event.payload.input_method), ['hotkey', 'mouse', 'hotkey']);
});

test('drags and resizes are mouse work', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage();
    const { component: wrapper } = canvasWrapper(page.core, page.job, {}, { [LOGGING]: page.logging });
    page.logging.trackInputJob(page.job);
    page.press('f');
    wrapper.onCanvasShapeDragged({ detail: { duration: 300, state: objectState({ clientID: 7 }) } });

    const [drag] = (await page.core.sent()).filter((event) => event.scope === 'drag:object');
    assert.equal(drag.payload.input_method, 'mouse');
});

test('nothing is counted in a 3D job', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const page = annotationPage({}, { job: { dimension: '3d' } });
    page.logging.trackInputJob(page.job);
    page.press('f');
    page.click('save');
    t.mock.timers.tick(120_000);
    page.click('save');
    page.logging.untrackInputJob();

    assert.deepEqual(await page.summaries(), []);
});

test('a failure inside the counting never affects the shortcut or the click', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-13T10:00:00Z') });
    const clicked = [];
    const page = annotationPage();
    page.window.document.getElementById('save').addEventListener('click', () => clicked.push('save'));
    const broken = {
        dimension: '2d',
        logger: { log() { throw new Error('logger broken'); } },
    };
    page.logging.trackInputJob(broken);
    t.mock.timers.tick(120_000);
    page.press('f');
    page.click('save');
    t.mock.timers.tick(120_000);
    page.press('f');
    page.logging.untrackInputJob();
    // an event without a target or a key event the counting cannot read
    page.logging.inputEvent(null);
    page.logging.inputEvent({ type: 'click', target: {} });

    assert.deepEqual(page.calls, ['NEXT_FRAME', 'NEXT_FRAME']);
    assert.deepEqual(clicked, ['save']);
});
