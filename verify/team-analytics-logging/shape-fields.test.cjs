// Ticket 09: the existing draw, paste, propagate, drag, resize and delete events carry the shape
// fields (and, for drag and resize, the object reference and frame). Driven through the UI's own
// call sites; observed in the batch the real cvat-core logger sends to the server.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, annotationActions, canvasWrapper, coreLogger, objectState, only, openJob,
} = require('./helper.cjs');

test('a drag of a box carries its shape, the object reference and the frame', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const { component } = canvasWrapper(core, job);
    component.onCanvasShapeDragged({
        detail: { duration: 850, state: objectState({ clientID: 7, serverID: 70, frame: 3 }) },
    });

    const event = only(await core.sent(), 'drag:object');
    assert.equal(event.duration, 850);
    assert.equal(event.obj_id, 70);
    assert.equal(event.job_id, 13);
    assert.equal(event.payload.shape_type, 'rectangle');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 1);
    assert.equal(event.payload.object_ref, 7);
    assert.equal(event.payload.frame, 3);
});

test('a resize of a polygon track names the shape and track and counts no box', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const { component } = canvasWrapper(core, job);
    component.onCanvasShapeResized({
        detail: {
            duration: 400,
            state: objectState({
                clientID: 9, serverID: undefined, shapeType: 'polygon', objectType: 'track', frame: 12,
            }),
        },
    });

    const event = only(await core.sent(), 'resize:object');
    assert.equal(event.obj_id, undefined);
    assert.equal(event.payload.shape_type, 'polygon');
    assert.equal(event.payload.object_type, 'track');
    assert.equal(event.payload.rectangle_count, 0);
    assert.equal(event.payload.object_ref, 9);
    assert.equal(event.payload.frame, 12);
});

test('the object reference does not replace the browser identifier the logger writes', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const { component } = canvasWrapper(core, job);
    component.onCanvasShapeDragged({ detail: { duration: 10, state: objectState({ clientID: 5 }) } });
    component.onCanvasShapeDragged({ detail: { duration: 10, state: objectState({ clientID: 6 }) } });

    const events = await core.sent();
    assert.deepEqual(events.map((event) => event.payload.object_ref), [5, 6]);
    assert.equal(events[0].payload.client_id, core.logger.clientID);
    assert.equal(events[1].payload.client_id, core.logger.clientID);
});

test('a box drawn from scratch is a single-frame rectangle', async () => {
    const core = coreLogger();
    const job = { ...openJob(core), labels: [{ id: 1, name: 'car' }] };
    const { component, created } = canvasWrapper(core, job, { activeObjectType: 'shape' });
    component.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'rectangle', points: [0, 0, 5, 5] }, duration: 1200, continue: false },
    });

    const event = only(await core.sent(), 'draw:object');
    assert.equal(event.count, 1);
    assert.equal(event.duration, 1200);
    assert.equal(event.payload.shape_type, 'rectangle');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 1);
    assert.equal(event.payload.object_ref, undefined);
    assert.equal(created.length, 1, 'the drawn object is still created');
});

test('a rectangle track drawn on the canvas counts no bounding box', async () => {
    const core = coreLogger();
    const job = { ...openJob(core), labels: [{ id: 1, name: 'car' }] };
    const { component } = canvasWrapper(core, job, { activeObjectType: 'track' });
    component.onCanvasShapeDrawn({
        detail: { state: { shapeType: 'rectangle', points: [0, 0, 5, 5] }, duration: 900, continue: false },
    });

    const event = only(await core.sent(), 'draw:object');
    assert.equal(event.payload.shape_type, 'rectangle');
    assert.equal(event.payload.object_type, 'track');
    assert.equal(event.payload.rectangle_count, 0);
});

test('a shape pasted onto the canvas carries its shape', async () => {
    const core = coreLogger();
    const job = { ...openJob(core), labels: [{ id: 1, name: 'car' }] };
    const { component } = canvasWrapper(core, job);
    component.onCanvasShapeDrawn({
        detail: {
            state: {
                shapeType: 'ellipse', objectType: 'shape', label: { id: 1 }, points: [0, 0, 5, 5],
            },
            duration: 300,
            continue: false,
        },
    });

    const event = only(await core.sent(), 'paste:object');
    assert.equal(event.payload.shape_type, 'ellipse');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 0);
});

test('a propagation counts the single-frame rectangles it creates', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const source = objectState({ clientID: 3, objectType: 'track' });
    job.annotations = { put: async () => [], get: async () => [] };
    job.actions = { get: async () => ({}) };
    const copies = [1, 2, 3].map((frame) => objectState({ clientID: undefined, frame, objectType: 'shape' }));
    const { actions, dispatch } = annotationActions(core, job, { states: [source], activated: 3 }, {
        utils: { propagateShapes: () => copies },
    });
    await dispatch(actions.propagateObjectAsync(0, 3));

    const event = only(await core.sent(), 'propagate:object');
    assert.equal(event.count, 3);
    assert.equal(event.payload.shape_type, 'rectangle');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 3);
});

test('a single deletion carries the deleted object\'s shape', async () => {
    const core = coreLogger();
    const job = openJob(core);
    job.actions = { get: async () => ({}) };
    const target = objectState({
        clientID: 4, shapeType: 'points', objectType: 'shape', delete: async () => true,
    });
    const { actions, dispatch } = annotationActions(core, job, { states: [target] });
    await dispatch(actions.removeObjectAsync(target, false));

    const event = only(await core.sent(), 'delete:object');
    assert.equal(event.count, 1);
    assert.equal(event.payload.shape_type, 'points');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 0);
});

test('deleting a selection describes only the objects that were removed', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const box = objectState({ clientID: 1 });
    const track = objectState({ clientID: 2, objectType: 'track' });
    const lockedPolygon = objectState({ clientID: 3, shapeType: 'polygon' });
    job.annotations = { removeBatch: async () => [1, 2] };
    const { actions, dispatch } = annotationActions(core, job, { states: [box, track, lockedPolygon], selected: [1, 2, 3] });
    await dispatch(actions.removeSelectionAsync(false));

    const event = only(await core.sent(), 'delete:object');
    assert.equal(event.count, 2);
    assert.equal(event.payload.shape_type, 'rectangle');
    assert.equal(event.payload.object_type, 'mixed');
    assert.equal(event.payload.rectangle_count, 1);
});

test('pasting a selection of several kinds of shape is mixed and counts its boxes', async () => {
    const core = coreLogger();
    const job = openJob(core);
    job.annotations = { put: async (states) => states.map((_, index) => 100 + index) };
    const copied = [
        { shapeType: 'rectangle', objectType: 'shape', points: [0, 0, 1, 1], frame: 0, elements: [] },
        { shapeType: 'rectangle', objectType: 'shape', points: [2, 2, 3, 3], frame: 0, elements: [] },
        { shapeType: 'polyline', objectType: 'shape', points: [0, 0, 1, 1], frame: 0, elements: [] },
    ];
    const { actions, dispatch } = annotationActions(core, job, { copied });
    await dispatch(actions.pasteSelectionAsync());
    await new Promise((resolve) => setTimeout(resolve, 0));

    const event = only(await core.sent(), 'paste:object');
    assert.equal(event.count, 3);
    assert.equal(event.payload.shape_type, 'mixed');
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.rectangle_count, 2);
});

test('every event goes to the server under a scope it accepts, with project, task and job', async () => {
    const core = coreLogger();
    const job = { ...openJob(core), labels: [{ id: 1, name: 'car' }] };
    const { component } = canvasWrapper(core, job);
    component.onCanvasShapeDrawn({ detail: { state: { shapeType: 'rectangle' }, duration: 5, continue: false } });
    component.onCanvasShapeDragged({ detail: { duration: 5, state: objectState() } });
    component.onCanvasShapeResized({ detail: { duration: 5, state: objectState() } });

    const events = await core.sent();
    assert.equal(events.length, 3);
    for (const event of events) {
        assert.ok(ALLOWED_SCOPES.has(event.scope), event.scope);
        assert.deepEqual([event.project_id, event.task_id, event.job_id], [11, 12, 13]);
    }
});
