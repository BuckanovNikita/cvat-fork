// Ticket 21: a frame-navigation hotkey is one hotkey action per frame it moves. The shortcut goes in
// through the UI's shortcut dispatcher (utils/mousetrap-react.tsx), runs the top bar's navigation
// (containers/annotation-page/top-bar/top-bar.tsx) and the real frame change (annotation-actions.ts
// changeFrameAsync) over a store that shows the frame it is given; the search keys run the real
// searchAnnotationsAsync. Clicks go in through the logging's window listeners (listenForInput, as
// cvat-app.tsx attaches them). Frames are fetched only when the test lets them load, so a key
// can be pressed and held while a frame is loading. The batch the real cvat-core logger sends comes out.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    coreLogger, dependency, domWindow, loadSource, openJob, uiBoundaries, withStubs,
} = require('./helper.cjs');

const React = dependency('react');
const LOGGING = 'utils/team-analytics-logging';
const SUMMARY = 'team_analytics:input_summary';
const TOP_BAR = 'cvat-ui/src/containers/annotation-page/top-bar/top-bar.tsx';
const ANNOTATION_ACTIONS = 'cvat-ui/src/actions/annotation-actions.ts';

const PAGE = `<!doctype html><html><body>
  <div class="cvat-annotation-header">
    <span id="next-button" class="anticon" role="img"></span><span id="prev-button" class="anticon" role="img"></span>
    <span id="search-button" class="anticon" role="img"></span>
    <div id="slider" class="ant-slider"><div id="slider-handle" class="ant-slider-handle" role="slider"></div></div>
  </div>
  <div class="cvat-objects-sidebar"><button id="sidebar-lock" class="ant-btn">Lock</button></div>
</body></html>`;

const KEY_MAP = {
    NEXT_FRAME: { name: 'Next frame', sequences: ['f'] },
    PREV_FRAME: { name: 'Previous frame', sequences: ['d'] },
    SEARCH_FORWARD: { name: 'Search forward', sequences: ['v'] },
    UNDO: { name: 'Undo', sequences: ['ctrl+z'] },
};

// reducers/index.ts: the values the top bar and the frame change compare with
const REDUCERS = withStubs({
    NavigationType: {
        REGULAR: 'regular', FILTERED: 'filtered', EMPTY: 'empty', CHAPTER: 'chapter',
    },
    Workspace: { STANDARD: 'Standard', REVIEW: 'Review' },
}, 'reducers');

/**
 * A job of frames 0..7 opened at `frame`, with its annotation page: the shortcut dispatcher, the top bar,
 * the frame change and the logging module, all sharing one store and one logger.
 */
function annotationPage({ frame = 3, job: jobOptions = {} } = {}) {
    const core = coreLogger();
    const loading = [];
    // what the annotation search finds: a frame number, or null; `searching` holds a search the test answers
    const search = { finds: null, slow: false, searching: [] };
    const job = {
        ...openJob(core, jobOptions),
        startFrame: 0,
        stopFrame: 7,
        frames: {
            // a frame arrives when the test lets it load
            get: (number) => new Promise((resolve) => { loading.push(() => resolve({ number, filename: `${number}.png` })); }),
            // no deleted frames: the search starts and ends where it is asked to
            search: async (filters, from) => from,
        },
        annotations: {
            get: async () => [],
            search: (from, to) => {
                if (!search.slow) return Promise.resolve(search.finds);
                return new Promise((resolve) => { search.searching.push(() => resolve(search.finds)); });
            },
        },
        actions: { get: async () => ({ undo: [], redo: [] }), recordSelection: async () => {} },
    };
    const state = {
        annotation: {
            annotations: {
                states: [], selectedStatesID: [], activatedStateID: null, filters: [], zLayer: { cur: 0, hiddenByFrame: new Map() },
            },
            player: { frame: { number: frame, changeTime: 0 }, navigationBlocked: false },
            job: { instance: job, groundTruthInfo: { groundTruthInstance: null, validationLayout: null } },
            propagate: { visible: false },
            statistics: { visible: false },
            workspace: 'Standard',
        },
        settings: {
            workspace: { showAllInterpolationTracks: false },
            shapes: { showGroundTruth: false },
            player: { frameSpeed: 1, showDeletedFrames: false },
        },
    };
    const store = { getState: () => state };
    const pending = [];
    // the reducer's part that matters here: a frame change shows its frame, and once the canvas has
    // drawn it CVAT's frame-change event is closed and joins the logger's collection
    const dispatch = (action) => {
        if (typeof action === 'function') {
            const running = action(dispatch, store.getState);
            pending.push(running);
            return running;
        }
        if (action.type === 'CHANGE_FRAME_SUCCESS') {
            state.annotation.player.frame.number = action.payload.number;
            action.payload.changeFrameEvent.close();
        }
        return action;
    };
    // utils/is-able-to-change-frame.ts: the canvas is ready, the frame is in the job, navigation not blocked
    const isAbleToChangeFrame = {
        __esModule: true,
        default: (number) => !state.annotation.player.navigationBlocked &&
            (typeof number !== 'number' || (number >= job.startFrame && number <= job.stopFrame)),
    };

    const logging = loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
    const boundaries = {
        ...uiBoundaries(core),
        [LOGGING]: logging,
        reducers: REDUCERS,
        'cvat-store': { getCVATStore: () => store },
        'utils/is-able-to-change-frame': isAbleToChangeFrame,
    };
    const actions = loadSource(ANNOTATION_ACTIONS, boundaries);
    const { default: connected } = loadSource(TOP_BAR, {
        ...boundaries,
        'actions/annotation-actions': actions,
        'react-router': { __esModule: true, withRouter: (component) => component },
    });
    const TopBar = connected.WrappedComponent;
    // the top bar reads the frame shown from the store at each use, as connect() hands it over
    const props = {
        jobInstance: job,
        playing: false,
        showDeletedFrames: false,
        navigationType: 'regular',
        frameStep: 10,
        onSwitchPlay() {},
        // top-bar.tsx mapDispatchToProps: the frame change and the annotation search, as the container wires them
        onChangeFrame: (number, fillBuffer) => dispatch(actions.changeFrameAsync(number, fillBuffer)),
        searchAnnotations: (session, from, to, filters) => dispatch(
            actions.searchAnnotationsAsync(session, from, to, filters),
        ),
    };
    Object.defineProperty(props, 'frameNumber', { get: () => state.annotation.player.frame.number });
    const topBar = new TopBar(props);

    // the player buttons (components/annotation-page/top-bar/player-buttons.tsx): hotkeys and buttons
    // run the same navigation
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
    GlobalHotKeys({
        keyMap,
        handlers: {
            NEXT_FRAME: () => { pending.push(topBar.onNextFrame()); },
            PREV_FRAME: () => { pending.push(topBar.onPrevFrame()); },
            SEARCH_FORWARD: () => { topBar.searchAnnotations('forward'); },
            UNDO: () => {},
        },
    });
    const window = domWindow(PAGE);
    window.document.getElementById('next-button').addEventListener('click', () => pending.push(topBar.onNextFrame()));
    window.document.getElementById('prev-button').addEventListener('click', () => pending.push(topBar.onPrevFrame()));
    window.document.getElementById('search-button').addEventListener('click', () => topBar.searchAnnotations('forward'));
    // the player slider (antd Slider) changes the frame as soon as the button goes down on it
    window.document.getElementById('slider').addEventListener('mousedown', () => {
        pending.push(topBar.onChangePlayerSliderValue(0));
    });
    // cvat-app.tsx: the logging's own window listeners, attached as the application attaches them
    logging.listenForInput(window);

    async function settle() {
        for (let round = 0; round < 50; round++) await new Promise((resolve) => { setImmediate(resolve); });
    }

    return {
        core,
        job,
        logging,
        state,
        search,
        get frame() { return state.annotation.player.frame.number; },
        /** A playback tick (top-bar.tsx handlePlayIfNecessary): the next frame, asked for with no input. */
        async tick() {
            props.onChangeFrame(state.annotation.player.frame.number + 1, true);
            await settle();
        },
        /** The frame number field (top-bar.tsx onChangePlayerInputValue), after the number is typed in. */
        async enterFrame(number) {
            pending.push(topBar.onChangePlayerInputValue(number));
            await settle();
        },
        /** The slow search answers. */
        async answerSearch() {
            search.searching.splice(0).forEach((resolve) => resolve());
            await settle();
        },
        /** A key press: the keydown reaches the window, then Mousetrap runs the shortcut bound to `sequence`. */
        async press(sequence, { repeat = false } = {}) {
            const event = new window.KeyboardEvent('keydown', { key: sequence, repeat, bubbles: true });
            window.document.body.dispatchEvent(event);
            bound[sequence](event, sequence);
            await settle(); // the frame is asked for; it has not loaded
        },
        async click(id) {
            const element = window.document.getElementById(id);
            element.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }));
            await settle();
            element.dispatchEvent(new window.MouseEvent('mouseup', { bubbles: true }));
            element.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
            await settle();
        },
        /** Every frame asked for so far loads, and what follows from it runs. */
        async load() {
            while (loading.length) {
                loading.splice(0).forEach((resolve) => resolve());
                await settle();
            }
            await Promise.all(pending.splice(0));
        },
        async summary() {
            this.logging.untrackInputJob();
            const summaries = (await core.sent()).filter((event) => event.obj_name === SUMMARY);
            assert.ok(summaries.length <= 1, JSON.stringify(summaries));
            return summaries.length ? summaries[0].payload : { hotkeys: {}, mouse: {} };
        },
    };
}

test('a frame-navigation key pressed and held while the frame is loading counts the one frame it moved', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    await page.press('f');
    for (let i = 0; i < 9; i++) await page.press('f', { repeat: true });
    assert.equal(page.frame, 3, 'the frame is still loading');
    await page.load();
    assert.equal(page.frame, 4);

    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, { NEXT_FRAME: 1 });
});

test('a held key on frames that load in time counts each frame moved', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 1 });
    page.logging.trackInputJob(page.job);
    await page.press('f');
    await page.load();
    for (let i = 0; i < 3; i++) {
        await page.press('f', { repeat: true });
        await page.load();
    }
    await page.press('d');
    await page.load();
    assert.equal(page.frame, 4);

    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, { NEXT_FRAME: 4, PREV_FRAME: 1 });
});

test('a frame-navigation key at the last or first frame, or while navigation is blocked, counts nothing', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 7 });
    page.logging.trackInputJob(page.job);
    await page.press('f');
    await page.press('f', { repeat: true });
    await page.load();
    assert.equal(page.frame, 7);

    page.state.annotation.player.frame.number = 0;
    await page.press('d');
    await page.load();
    page.state.annotation.player.frame.number = 3;
    page.state.annotation.player.navigationBlocked = true;
    await page.press('f');
    await page.press('d');
    await page.load();
    assert.equal(page.frame, 3);

    // a later frame change with the mouse is not one of these keys
    page.state.annotation.player.navigationBlocked = false;
    await page.click('next-button');
    await page.load();
    assert.equal(page.frame, 4);

    const { hotkeys, mouse } = await page.summary();
    assert.deepEqual(hotkeys, {});
    assert.deepEqual(mouse, { header: 1 });
});

test('a frame change that starts as the mouse button goes down is not a hotkey action', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 7 });
    page.logging.trackInputJob(page.job);
    await page.press('f'); // at the last frame: it moves nothing
    await page.click('slider-handle'); // the slider goes to the first frame before its click arrives
    await page.load();
    assert.equal(page.frame, 0);

    const { hotkeys, mouse } = await page.summary();
    assert.deepEqual(hotkeys, {});
    assert.deepEqual(mouse, { header: 1 });
});

test('a frame change made with the mouse is not a hotkey action, even when a key is pressed while it loads', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    await page.click('next-button');
    await page.press('f'); // asks for the frame the click is already loading
    await page.load();
    assert.equal(page.frame, 4);
    await page.click('prev-button');
    await page.load();
    assert.equal(page.frame, 3);

    const { hotkeys, mouse } = await page.summary();
    assert.deepEqual(hotkeys, {});
    assert.deepEqual(mouse, { header: 2 });
});

test('other held keys stay one hotkey action and CVAT logs each frame change as before', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    await page.press('ctrl+z');
    for (let i = 0; i < 4; i++) await page.press('ctrl+z', { repeat: true });
    await page.press('f');
    await page.press('f', { repeat: true });
    await page.load();
    await page.click('sidebar-lock');
    await page.press('f');
    await page.load();

    const sent = await page.core.sent();
    const changes = sent.filter((event) => event.scope === 'change:frame');
    // CVAT's own events, as before this ticket: every frame change it made, the request repeated while
    // the frame loaded included (3 -> 4 twice, then 4 -> 5, compressed by the logger)
    assert.deepEqual(
        changes.map((event) => [event.payload.from, event.payload.to, event.count]),
        [[3, 4, 1], [3, 5, 2]],
    );
    const { hotkeys, mouse } = await page.summary();
    assert.deepEqual(hotkeys, { UNDO: 1, NEXT_FRAME: 2 });
    assert.deepEqual(mouse, { objects_sidebar: 1 });
});

test('a failure inside the counting never reaches the frame change or the shortcut', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    const broken = { ...page.job };
    Object.defineProperty(broken, 'dimension', { get() { throw new Error('cannot read dimension'); } });
    page.logging.trackInputJob(broken);
    await page.press('f');
    await page.load();
    assert.equal(page.frame, 4);

    const changes = (await page.core.sent()).filter((event) => event.scope === 'change:frame');
    assert.equal(changes.length, 1);
    assert.deepEqual([changes[0].payload.from, changes[0].payload.to], [3, 4]);
});

test('a failure in counting the frame shown never reaches the frame change', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-14T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    // the job can be read until its frame has loaded, so the counting fails only at the frame shown
    let readable = true;
    const broken = { ...page.job };
    Object.defineProperty(broken, 'dimension', {
        get() {
            if (readable) return '2d';
            throw new Error('cannot read dimension');
        },
    });
    const { get } = page.job.frames;
    page.job.frames.get = async (number) => {
        const data = await get(number);
        readable = false;
        return data;
    };
    page.logging.trackInputJob(broken);
    await page.press('f');
    await page.load();
    assert.equal(page.frame, 4);

    const changes = (await page.core.sent()).filter((event) => event.scope === 'change:frame');
    assert.deepEqual(changes.map((event) => [event.payload.from, event.payload.to, event.count]), [[3, 4, 1]]);
});

// Review of 2026-11-15, finding 1: a key counts only a frame change its own handler starts.

test('a key that moves nothing is not credited with the next playback step', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    page.state.annotation.player.navigationBlocked = true;
    await page.press('f');
    await page.load();
    page.state.annotation.player.navigationBlocked = false;
    await page.tick();
    await page.load();
    assert.equal(page.frame, 4);

    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, {});
});

test('a search key that finds nothing during playback is not credited with the playback steps after it', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    page.search.finds = null;
    await page.press('v');
    await page.tick();
    await page.load();
    await page.tick();
    await page.load();
    assert.equal(page.frame, 5);

    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, {});
});

test('a key at the last frame is not credited with a frame entered in the frame number field', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage({ frame: 7 });
    page.logging.trackInputJob(page.job);
    await page.press('f');
    await page.load();
    assert.equal(page.frame, 7);
    await page.enterFrame(2);
    await page.load();
    assert.equal(page.frame, 2);

    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, {});
});

test('a key that moves nothing is not credited with the frame change of a search already running', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    page.search.slow = true;
    page.search.finds = 6;
    await page.click('search-button'); // the search runs until the test answers it
    page.state.annotation.player.navigationBlocked = true;
    await page.press('f');
    page.state.annotation.player.navigationBlocked = false;
    await page.answerSearch();
    await page.load();
    assert.equal(page.frame, 6);

    const { hotkeys, mouse } = await page.summary();
    assert.deepEqual(hotkeys, {});
    assert.deepEqual(mouse, { header: 1 });
});

test('a search key counts the frame it found, and a key pressed while that frame loads counts its own', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const page = annotationPage({ frame: 3 });
    page.logging.trackInputJob(page.job);
    page.search.finds = 6;
    await page.press('v'); // the search finds frame 6 and its frame change starts: frame 6 is loading
    await page.press('d'); // asks for frame 2 while frame 6 loads
    await page.load();

    const changes = (await page.core.sent()).filter((event) => event.scope === 'change:frame');
    assert.deepEqual(changes.map((event) => [event.payload.from, event.payload.to]), [[3, 6], [3, 2]]);
    const { hotkeys } = await page.summary();
    assert.deepEqual(hotkeys, { SEARCH_FORWARD: 1, PREV_FRAME: 1 });
});
