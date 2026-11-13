// Ticket 09: the added logging stays out of the way. Only 2D jobs are instrumented, nothing is recorded
// outside a job, a failure inside the logging never reaches the caller, and annotation goes on as before.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, annotationActions, canvasWrapper, coreLogger, loadSource, objectState, only, openJob,
    uiBoundaries,
} = require('./helper.cjs');

const NEW_FIELDS = ['shape_type', 'rectangle_count', 'object_type', 'input_method', 'object_ref', 'frame'];

function newFields(event) {
    return NEW_FIELDS.filter((key) => key in event.payload);
}

// An object the logging cannot read: every field access throws.
function unreadable(fields = {}) {
    const state = objectState(fields);
    for (const key of ['shapeType', 'objectType', 'clientID', 'frame']) {
        Object.defineProperty(state, key, { get() { throw new Error(`cannot read ${key}`); } });
    }
    return state;
}

function loggingModule(core) {
    return loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
}

test('in a 3D job a deletion is sent exactly as before, without shape fields', async () => {
    const core = coreLogger();
    const job = openJob(core, { dimension: '3d' });
    job.actions = { get: async () => ({}) };
    const cuboid = objectState({ clientID: 4, shapeType: 'cuboid', delete: async () => true });
    const { actions, dispatch, dispatched } = annotationActions(core, job, { states: [cuboid] });
    await dispatch(actions.removeObjectAsync(cuboid, false));

    const event = only(await core.sent(), 'delete:object');
    assert.equal(event.count, 1);
    assert.deepEqual(newFields(event), []);
    assert.deepEqual(dispatched.map((action) => action.type), ['REMOVE_OBJECT_SUCCESS']);
});

test('a drag whose object cannot be read is still logged as before and the caller does not see the failure', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const { component } = canvasWrapper(core, job);
    const state = unreadable({ serverID: 70 });
    // serverID stays readable: the stock part of the event is unchanged
    Object.defineProperty(state, 'serverID', { value: 70 });
    assert.doesNotThrow(() => component.onCanvasShapeDragged({ detail: { duration: 300, state } }));

    const event = only(await core.sent(), 'drag:object');
    assert.equal(event.duration, 300);
    assert.equal(event.obj_id, 70);
    assert.deepEqual(newFields(event), []);
});

test('a deletion goes ahead when the logging fails on its objects', async () => {
    const core = coreLogger();
    const job = openJob(core);
    job.actions = { get: async () => ({}) };
    const target = unreadable({ clientID: 4 });
    Object.defineProperty(target, 'clientID', { value: 4 });
    target.delete = async () => true;
    const { actions, dispatch, dispatched } = annotationActions(core, job, { states: [target] });
    await dispatch(actions.removeObjectAsync(target, false));

    assert.deepEqual(dispatched.map((action) => action.type), ['REMOVE_OBJECT_SUCCESS']);
    const event = only(await core.sent(), 'delete:object');
    assert.equal(event.count, 1);
    assert.deepEqual(newFields(event), []);
});

test('after repeated failures the logging switches itself off', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const { component } = canvasWrapper(core, job);
    for (let attempt = 0; attempt < 3; attempt += 1) {
        component.onCanvasShapeDragged({ detail: { duration: 10, state: unreadable() } });
    }
    component.onCanvasShapeDragged({ detail: { duration: 10, state: objectState({ clientID: 8 }) } });

    const events = await core.sent();
    assert.equal(events.length, 4, 'every drag is still logged');
    assert.deepEqual(newFields(events[3]), [], 'a readable object after the switch-off gets no fields');
});

test('a record is sent through the job as a debug record carrying project, task and job', async () => {
    const core = coreLogger();
    const logging = loggingModule(core);
    logging.logRecord(openJob(core), logging.RECORD.classChange, { shape_type: 'rectangle' }, 2);

    const event = only(await core.sent(), 'debug:info');
    assert.ok(ALLOWED_SCOPES.has(event.scope));
    assert.equal(event.obj_name, 'team_analytics:class_change');
    assert.equal(event.count, 2);
    assert.deepEqual([event.project_id, event.task_id, event.job_id], [11, 12, 13]);
    assert.equal(event.payload.shape_type, 'rectangle');
});

test('nothing is recorded outside a job or outside the 2D canvas', async () => {
    const core = coreLogger();
    const logging = loggingModule(core);
    logging.logRecord(null, logging.RECORD.inputSummary, {});
    logging.logRecord(undefined, logging.RECORD.inputSummary, {});
    logging.logRecord(openJob(core, { dimension: '3d' }), logging.RECORD.inputSummary, {});
    assert.deepEqual(logging.operationFields(null, [objectState()]), {});
    assert.deepEqual(logging.alignmentFields(undefined, objectState()), {});

    assert.deepEqual(await core.sent(), []);
});

test('a record the logger refuses does not reach the caller', async () => {
    const core = coreLogger();
    const logging = loggingModule(core);
    const job = openJob(core);
    job.logger.log = async () => { throw new Error('rejected'); };
    assert.doesNotThrow(() => logging.logRecord(job, logging.RECORD.modelCreation, { rectangle_count: 1 }, 1));
    const throwing = openJob(core);
    throwing.logger.log = () => { throw new Error('thrown'); };
    assert.doesNotThrow(() => logging.logRecord(throwing, logging.RECORD.modelCreation, {}, 1));
    // an unhandled rejection would fail this test file
    await new Promise((resolve) => setTimeout(resolve, 10));
});

test('a record never overwrites the browser identifier', async () => {
    const core = coreLogger();
    const logging = loggingModule(core);
    logging.logRecord(openJob(core), logging.RECORD.inputSummary, { client_id: 'mine' });

    const event = only(await core.sent(), 'debug:info');
    assert.equal(event.payload.client_id, core.logger.clientID);
});
