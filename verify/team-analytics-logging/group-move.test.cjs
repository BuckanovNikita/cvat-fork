// Ticket 22: a group move (selected objects dragged together, or the selection box moved) is one
// drag:object event for the gesture, carrying the objects moved; CVAT's own drag of the grabbed object
// is still sent, marked so that it is not counted again. Driven through the canvas wrapper's handlers in
// the order the canvas dispatches them (canvas.groupmoved, then canvas.dragshape for a grabbed object,
// in the same task); observed in the batch the real cvat-core logger sends to the server.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, canvasWrapper, coreLogger, objectState, openJob,
} = require('./helper.cjs');

const POLYGON = { shapeType: 'polygon', objectType: 'shape' };

function wrapper(core, job) {
    const batches = [];
    const selections = [];
    const { component } = canvasWrapper(core, job, {
        selectedStatesID: [1, 2, 3],
        onUpdateAnnotationsBatch: async (states) => { batches.push(states); },
        onSelectObjects: (ids) => { selections.push(ids); },
    });
    return { component, batches, selections };
}

// The canvas's group event: every object moved with its new points.
function groupMoved(states, duration) {
    return { detail: { duration, states: states.map((state) => ({ state, points: [0, 0, 1, 1] })) } };
}

function boxes(...ids) {
    return ids.map((id) => objectState({ clientID: id, serverID: id * 10, frame: 3 }));
}

async function drags(core) {
    const events = await core.sent();
    for (const event of events) assert.ok(ALLOWED_SCOPES.has(event.scope), event.scope);
    return events.filter((event) => event.scope === 'drag:object');
}

function assertGroupEvent(event, { objects, rectangles, shapeType, duration }) {
    assert.equal(event.payload.group, 'move');
    assert.equal(event.count, objects);
    assert.equal(event.duration, duration);
    assert.equal(event.job_id, 13);
    assert.equal(event.payload.rectangle_count, rectangles);
    assert.equal(event.payload.shape_type, shapeType);
    assert.equal(event.payload.object_type, 'shape');
    assert.equal(event.payload.frame, 3);
    assert.equal(event.payload.input_method, 'mouse');
    assert.equal('object_ref' in event.payload, false, 'a group event refers to no single object');
    assert.equal(event.obj_id, undefined);
}

test('a group drag of three boxes sends one group event for three objects and marks CVAT\'s own drag', async () => {
    const core = coreLogger();
    const { component, batches } = wrapper(core, openJob(core));
    const moved = boxes(1, 2, 3);
    // the canvas dispatches both in the same task, without waiting for the first handler
    const persisted = component.onCanvasObjectsGroupMoved(groupMoved(moved, 900));
    component.onCanvasShapeDragged({ detail: { duration: 900, state: moved[1] } });
    await persisted;

    const events = await drags(core);
    const groups = events.filter((event) => event.payload.group === 'move');
    assert.equal(groups.length, 1, `one group event, got ${JSON.stringify(events)}`);
    assertGroupEvent(groups[0], {
        objects: 3, rectangles: 3, shapeType: 'rectangle', duration: 900,
    });

    // CVAT's own log of the grabbed box is still sent, as before, and marked as part of the group
    const own = events.filter((event) => event.payload.group !== 'move');
    assert.equal(own.length, 1);
    assert.equal(own[0].obj_id, 20);
    assert.equal(own[0].duration, 900);
    assert.equal(own[0].payload.object_ref, 2);
    assert.equal(own[0].payload.group, 'grabbed');

    assert.equal(batches.length, 1, 'the move is still saved as one change');
    assert.equal(batches[0].length, 3);
});

test('moving the selection box sends the same group event', async () => {
    const core = coreLogger();
    const { component, batches, selections } = wrapper(core, openJob(core));
    await component.onCanvasObjectsGroupMoved(groupMoved(boxes(1, 2, 3), 1200));

    const events = await drags(core);
    assert.equal(events.length, 1, `one drag event, got ${JSON.stringify(events)}`);
    assertGroupEvent(events[0], {
        objects: 3, rectangles: 3, shapeType: 'rectangle', duration: 1200,
    });
    assert.equal(batches.length, 1);
    assert.deepEqual(selections, [[1, 2, 3]]);
});

test('a later drag of an object that was moved with the selection box is a single drag again', async () => {
    const core = coreLogger();
    const { component } = wrapper(core, openJob(core));
    const moved = boxes(1, 2, 3);
    await component.onCanvasObjectsGroupMoved(groupMoved(moved, 1200));
    // the next drag comes with a later mouse gesture, in another task
    await new Promise((resolve) => { setTimeout(resolve, 0); });
    component.onCanvasShapeDragged({ detail: { duration: 300, state: moved[0] } });

    const events = await drags(core);
    assert.equal(events.length, 2);
    assert.equal(events[1].payload.object_ref, 1);
    assert.equal('group' in events[1].payload, false);
});

test('a group of boxes and other shapes says how many of its objects are boxes', async () => {
    const core = coreLogger();
    const { component } = wrapper(core, openJob(core));
    const moved = [...boxes(1, 2), objectState({ clientID: 3, frame: 3, ...POLYGON })];
    await component.onCanvasObjectsGroupMoved(groupMoved(moved, 600));

    const [event] = await drags(core);
    assertGroupEvent(event, {
        objects: 3, rectangles: 2, shapeType: 'mixed', duration: 600,
    });
});

test('when the group cannot be read the move goes ahead and the grabbed drag is a single drag as before', async () => {
    const core = coreLogger();
    const { component, batches } = wrapper(core, openJob(core));
    const moved = boxes(1, 2, 3);
    // the logging cannot read the other two objects: every field it reads throws
    for (const state of [moved[0], moved[2]]) {
        for (const key of ['shapeType', 'objectType', 'clientID', 'frame']) {
            Object.defineProperty(state, key, { get() { throw new Error(`cannot read ${key}`); } });
        }
    }
    let persisted;
    assert.doesNotThrow(() => { persisted = component.onCanvasObjectsGroupMoved(groupMoved(moved, 900)); });
    component.onCanvasShapeDragged({ detail: { duration: 900, state: moved[1] } });
    await persisted;

    const events = await drags(core);
    assert.equal(events.length, 1, 'no group event');
    assert.equal(events[0].payload.object_ref, 2);
    assert.equal('group' in events[0].payload, false, 'the grabbed drag counts as before');
    assert.equal(batches.length, 1, 'the move is still saved');
});

test('a logger that refuses the group event does not reach the canvas handler', async () => {
    const core = coreLogger();
    const job = openJob(core);
    job.logger.log = () => Promise.reject(new Error('refused'));
    const { component, batches } = wrapper(core, job);
    await component.onCanvasObjectsGroupMoved(groupMoved(boxes(1, 2, 3), 900));
    await new Promise((resolve) => { setTimeout(resolve, 0); });

    // an unhandled rejection would fail this test file
    assert.equal(batches.length, 1);
});

test('in a 3D job a group move sends nothing new', async () => {
    const core = coreLogger();
    const { component, batches } = wrapper(core, openJob(core, { dimension: '3d' }));
    await component.onCanvasObjectsGroupMoved(groupMoved(boxes(1, 2, 3), 900));

    assert.deepEqual(await drags(core), []);
    assert.equal(batches.length, 1);
});
