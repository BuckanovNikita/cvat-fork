// Ticket 18 (final run): the input summary written when a job closes must leave with the save the
// annotation view makes as it closes. On the test stack the record stayed behind for CVAT's next
// periodic save (90 s), so closing the tab soon after leaving a job lost it.
//
// The annotation view (components/annotation-page/annotation-page.tsx) is rendered shallowly with a
// recording `react`; its unmount cleanup runs; the batches the real cvat-core logger POSTs come out.
// The job's logger goes through cvat-core's plugin wrapper twice, as Job.logger.log does in the
// browser (session.ts -> session-implementation.ts -> logger.ts), so the record reaches the logger
// as late as it does there.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    coreLogger, domWindow, loadSource, uiBoundaries,
} = require('./helper.cjs');

const SUMMARY = 'team_analytics:input_summary';
const LOGGING = 'utils/team-analytics-logging';

function browserJob(core) {
    const { default: PluginRegistry } = loadSource('cvat-core/src/plugins.ts');
    const job = {
        id: 13, projectId: 11, taskId: 12, dimension: '2d',
    };
    // session.ts: Job.prototype.logger.log -> PluginRegistry.apiWrapper -> its implementation
    const log = async (scope, payload = {}, wait = false) => PluginRegistry.apiWrapper.call(job, log, scope, payload, wait);
    log.implementation = async (scope, payload, wait) => core.logger.log(scope, {
        ...payload, project_id: job.projectId, task_id: job.taskId, job_id: job.id,
    }, wait);
    job.logger = { log };
    return job;
}

function annotationView(core, job, logging) {
    const effects = [];
    const react = {
        __esModule: true,
        createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
        Fragment: 'Fragment',
        useEffect: (effect) => { effects.push(effect); },
        useState: (initial) => [initial, () => {}],
        useRef: (initial) => ({ current: initial }),
        useCallback: (fn) => fn,
        useMemo: (fn) => fn(),
        memo: (component) => component,
        forwardRef: (component) => component,
        lazy: (load) => load,
        createContext: () => ({ Provider: 'Provider', Consumer: 'Consumer' }),
        useContext: () => ({}),
    };
    react.default = react;
    const { default: AnnotationPage } = loadSource('cvat-ui/src/components/annotation-page/annotation-page.tsx', {
        ...uiBoundaries(core),
        react,
        [LOGGING]: logging,
        'utils/event-recorder': { __esModule: true, default: { logger: null } },
        'utils/hooks': { __esModule: true, usePrevious: () => undefined },
    });
    const saves = [];
    AnnotationPage({
        job,
        fetching: false,
        annotationsInitialized: true,
        workspace: 'Standard',
        frameNumber: 0,
        getJob() {},
        saveLogs() { saves.push(core.logger.save()); },
        closeJob() {},
        changeFrame() {},
    });
    // the view sets the page's minimum height on #root while mounted
    globalThis.window = domWindow('<!doctype html><html><body><div id="root"></div></body></html>');
    const cleanups = effects.map((effect) => effect()).filter((cleanup) => typeof cleanup === 'function');
    return {
        saves,
        async unmount() {
            cleanups.forEach((cleanup) => cleanup());
            delete globalThis.window;
            await Promise.all(saves);
            await new Promise((resolve) => { setImmediate(resolve); });
            await Promise.all(saves);
        },
    };
}

test('the summary written as the annotation view closes is in the save it makes as it closes', async () => {
    const core = coreLogger();
    const job = browserJob(core);
    const logging = loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
    const view = annotationView(core, job, logging);
    logging.trackInputJob(job);
    logging.hotkeyUsed('UNDO', { repeat: false });
    logging.hotkeyUsed('UNDO', { repeat: false });

    await view.unmount();

    // only what the view's own saves POSTed: no later periodic save has run
    const sent = core.posts.flatMap((body) => body.events)
        .map((event) => ({ ...event, payload: event.payload ? JSON.parse(event.payload) : {} }));
    const summaries = sent.filter((event) => event.obj_name === SUMMARY);
    assert.equal(summaries.length, 1, `events POSTed as the view closed: ${JSON.stringify(sent.map((e) => e.scope))}`);
    assert.deepEqual(summaries[0].payload.hotkeys, { UNDO: 2 });
    assert.deepEqual([summaries[0].project_id, summaries[0].task_id, summaries[0].job_id], [11, 12, 13]);
});

test('a failing logger at close neither throws nor stops the closing save', async () => {
    const core = coreLogger();
    const job = browserJob(core);
    const logging = loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
    const view = annotationView(core, job, logging);
    logging.trackInputJob(job);
    logging.hotkeyUsed('UNDO', { repeat: false });
    core.logger.log('click:element', { obj_name: 'cvat-header-tasks-button' });
    job.logger.log = () => Promise.reject(new Error('logger broken'));

    await view.unmount();

    const sent = core.posts.flatMap((body) => body.events);
    assert.equal(sent.filter((event) => event.scope === 'click:element').length, 1, 'the closing save still ran');
    assert.equal(sent.filter((event) => event.obj_name === SUMMARY).length, 0);
});
