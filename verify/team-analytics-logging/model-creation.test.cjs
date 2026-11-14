// Ticket 12: boxes the built-in detector makes in the annotation view are recorded as one `debug:info`
// record named `team_analytics:model_creation`, with `rectangle_count` = the single-frame rectangles it
// created and `count` = every object it created. Driven through the detector's `runInference` callback of
// the AI tools control (tools-control.tsx); observed in the batch the real cvat-core logger sends.
// A failure inside the recording never changes what the detector does.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, annotationActions, coreLogger, loadSource, openJob, uiBoundaries,
} = require('./helper.cjs');

const RECORD = 'team_analytics:model_creation';
const TOOLS_CONTROL = 'cvat-ui/src/components/annotation-page/standard-workspace/controls-side-bar/tools-control.tsx';
const CAR = { id: 1, name: 'car', type: 'any', attributes: [], structure: null };

// tools-control.tsx reads localStorage when constructed; node has none.
if (typeof globalThis.localStorage === 'undefined') {
    const items = new Map();
    globalThis.localStorage = {
        getItem: (key) => (items.has(key) ? items.get(key) : null),
        setItem: (key, value) => items.set(key, String(value)),
        removeItem: (key) => items.delete(key),
    };
}

// cvat-core's ObjectState as the detector builds it: the serialized fields, as given.
class FakeObjectState {
    constructor(serialized) { Object.assign(this, serialized); }
}

function detection(shapes = [], tags = []) {
    return {
        shapes: shapes.map((type) => ({
            type, label_id: CAR.id, attributes: [], points: [0, 0, 1, 1], occluded: false, rotation: 0,
        })),
        tags: tags.map(() => ({ label_id: CAR.id, attributes: [] })),
    };
}

/**
 * The AI tools control for `job`, its detector answering with `result` (or failing with an Error).
 * Returns `run()` (runs inference as the detector runner does), the states handed to `createAnnotations`
 * and the error notifications shown.
 */
function toolsControl(core, job, result, ObjectState = FakeObjectState, { createFails = false } = {}) {
    const notifications = [];
    const created = [];
    // `createAnnotations` is the real thunk (annotation-actions.ts createAnnotationsAsync), as connect()
    // binds it; the job's collection creates the objects or fails
    const annotations = {
        put: async (states) => {
            if (createFails) throw new Error('could not create the objects');
            created.push(...states);
            return states.map((_, index) => 100 + index);
        },
        get: async () => [],
    };
    const jobWithAnnotations = { ...job, labels: [CAR], annotations };
    const { actions, dispatch, dispatched } = annotationActions(core, jobWithAnnotations, {}, {
        classes: { ObjectState },
    });
    const module = loadSource(TOOLS_CONTROL, {
        ...uiBoundaries(core, {
            classes: { ObjectState },
            lambda: {
                call: async () => {
                    if (result instanceof Error) throw result;
                    return result;
                },
            },
        }),
        'antd/lib/notification': { __esModule: true, default: { error: (args) => notifications.push(args) } },
    });
    const component = new module.ToolsControlComponent({
        jobInstance: jobWithAnnotations,
        labels: [CAR],
        interactors: [],
        detectors: [],
        trackers: [],
        frame: 4,
        currentZOrder: 0,
        defaultApproxPolyAccuracy: 0.5,
        frameData: { width: 100, height: 100 },
        createAnnotations: (states) => dispatch(actions.createAnnotationsAsync(states)),
    });
    component.setState = () => {};
    const runner = component.renderDetectorBlock();
    return {
        run: () => runner.props.runInference({ id: 'detector' }, { mapping: {} }),
        created,
        notifications,
        dispatched,
    };
}

function records(events) {
    return events.filter((event) => event.scope === 'debug:info' && event.obj_name === RECORD);
}

test('a detector run sends one model creation record with its rectangles and every object it made', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const control = toolsControl(core, job, detection(['rectangle', 'rectangle', 'polygon'], ['tag']));

    await control.run();

    assert.equal(control.created.length, 4);
    const events = await core.sent();
    const [record] = records(events);
    assert.equal(records(events).length, 1);
    assert.equal(record.count, 4);
    assert.equal(record.payload.rectangle_count, 2);
    assert.deepEqual([record.project_id, record.task_id, record.job_id], [11, 12, 13]);
    for (const event of events) assert.ok(ALLOWED_SCOPES.has(event.scope), event.scope);
});

test('a detector run that finds nothing records nothing', async () => {
    const core = coreLogger();
    const control = toolsControl(core, openJob(core), detection([]));

    await control.run();

    assert.deepEqual(records(await core.sent()), []);
});

test('a detector that fails records nothing and shows its error as before', async () => {
    const core = coreLogger();
    const control = toolsControl(core, openJob(core), new Error('model is down'));

    await control.run();

    assert.deepEqual(records(await core.sent()), []);
    assert.equal(control.notifications.length, 1);
});

test('detected objects that could not be created are not recorded', async () => {
    const core = coreLogger();
    const control = toolsControl(core, openJob(core), detection(['rectangle', 'rectangle', 'polygon']),
        FakeObjectState, { createFails: true });

    await control.run();

    assert.deepEqual(control.created, []);
    assert.ok(control.dispatched.some((action) => action.type === 'CREATE_ANNOTATIONS_FAILED'));
    assert.deepEqual(records(await core.sent()), []);
});

test('outside the 2D canvas nothing is recorded', async () => {
    const core = coreLogger();
    const control = toolsControl(core, openJob(core, { dimension: '3d' }), detection(['rectangle']));

    await control.run();

    assert.equal(control.created.length, 1);
    assert.deepEqual(records(await core.sent()), []);
});

test('a failure inside the recording never affects the detector result', async (t) => {
    const failures = {
        'the logger throws': () => { throw new Error('logger broken'); },
        'the logger rejects': () => Promise.reject(new Error('logger broken')),
    };
    for (const [name, log] of Object.entries(failures)) {
        await t.test(name, async () => {
            const core = coreLogger();
            const job = { ...openJob(core), logger: { log } };
            const control = toolsControl(core, job, detection(['rectangle', 'polygon']));

            await control.run();
            await new Promise((resolve) => setImmediate(resolve));

            assert.equal(control.created.length, 2);
            assert.deepEqual(control.notifications, []);
        });
    }

    await t.test('an object whose fields cannot be read', async () => {
        const core = coreLogger();
        class BrokenState extends FakeObjectState {
            get shapeType() { throw new Error('broken state'); }

            set shapeType(value) { /* kept nowhere */ }
        }
        const control = toolsControl(core, openJob(core), detection(['rectangle']), BrokenState);

        await control.run();

        assert.equal(control.created.length, 1);
        assert.deepEqual(control.notifications, []);
    });
});
