// Ticket 10: changing the label of an existing object sends one class change record (a `debug:info`
// event named `team_analytics:class_change`) with the number of objects whose label changed, their shape
// fields and the input method. Driven through the UI's own entry points (object sidebar item, label
// hotkeys, selection context menu, attribute annotation sidebar); observed in the batch the real
// cvat-core logger sends to the server.
//
// Function components are rendered shallowly: `react` is replaced by a recording `createElement` and
// trivial hooks, so a test calls the component, finds the element that carries the handler the user
// triggers (`handlers`, `onChange`, `changeLabel`) and invokes it.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    ALLOWED_SCOPES, coreLogger, loadSource, objectState, openJob, uiBoundaries,
} = require('./helper.cjs');

const RECORD = 'team_analytics:class_change';
const CAR = { id: 1, name: 'car', type: 'any', attributes: [] };
const BUS = { id: 2, name: 'bus', type: 'any', attributes: [] };
const LABELS = [CAR, BUS];

// ---- shallow rendering -------------------------------------------------------------------------------

function fakeReact() {
    const react = {
        __esModule: true,
        Fragment: 'Fragment',
        createElement(type, props, ...children) {
            return { type, props: { ...(props || {}), children } };
        },
        useState: (initial) => [typeof initial === 'function' ? initial() : initial, () => {}],
        useRef: (current) => ({ current }),
        useEffect: () => {},
        useLayoutEffect: () => {},
        useMemo: (make) => make(),
        useCallback: (callback) => callback,
        memo: (component) => component,
        forwardRef: (component) => component,
        Component: class Component { constructor(props) { this.props = props; } },
        PureComponent: class PureComponent { constructor(props) { this.props = props; } },
    };
    react.default = react;
    return react;
}

/** Every element below `tree` (props included) for which `predicate` holds. */
function findElements(tree, predicate, found = [], seen = new Set()) {
    if (!tree || typeof tree !== 'object' || seen.has(tree)) return found;
    seen.add(tree);
    if (Array.isArray(tree)) {
        for (const item of tree) findElements(item, predicate, found, seen);
        return found;
    }
    if ('type' in tree && 'props' in tree) {
        if (predicate(tree)) found.push(tree);
        for (const value of Object.values(tree.props)) findElements(value, predicate, found, seen);
    }
    return found;
}

function findElement(tree, predicate, what) {
    const found = findElements(tree, predicate);
    assert.equal(found.length, 1, `one ${what}`);
    return found[0];
}

// An object state as the UI holds it, with a label.
function labelled(fields = {}) {
    return objectState({
        label: CAR, elements: [], lock: false, isGroundTruth: false, attributes: {}, zOrder: 0, outside: false, hidden: false,
        ...fields,
    });
}

function store(job, { states = [], selected = [], activated = null } = {}) {
    const state = {
        annotation: {
            annotations: {
                states, selectedStatesID: selected, activatedStateID: activated, zLayer: { min: 0, max: 0 },
            },
            job: { instance: job, labels: LABELS },
            drawing: { activeShapeType: 'rectangle', activeObjectType: 'shape' },
            player: { frame: { number: 0 } },
            canvas: { instance: null },
            workspace: 'Standard',
        },
        shortcuts: { keyMap: {}, normalizedKeyMap: {} },
    };
    return { getState: () => state };
}

// What the sites use around the label change; the save is recorded in `saved`.
function siteBoundaries(core, appStore, saved) {
    return {
        ...uiBoundaries(core),
        react: fakeReact(),
        'react-redux': {
            useDispatch: () => (action) => action,
            useSelector: (select) => select(appStore.getState()),
            connect: () => (component) => component,
        },
        'cvat-store': { getCVATStore: () => appStore },
        'actions/annotation-actions': new Proxy({
            updateAnnotationsAsync: (states) => saved.push({ batch: false, labels: states.map((s) => s.label.id) }),
            updateAnnotationsBatchAsync: (states) => saved.push({ batch: true, labels: states.map((s) => s.label.id) }),
        }, { get: (target, key) => target[key] ?? (() => ({ type: String(key) })) }),
        'utils/mousetrap-react': { __esModule: true, default: 'GlobalHotKeys' },
        'utils/filter-applicable-labels': { filterApplicableLabels: (state, labels) => labels },
        'utils/multi-selection': new Proxy({
            getSelectedStates: (states, ids) => states.filter((state) => ids.includes(state.clientID)),
            getSelectionAttributeState: () => ({ attributes: [] }),
            getSelectionGroupState: () => ({ canGroup: false }),
            isMultiSelectObjectModifierPressed: () => false,
        }, { get: (target, key) => target[key] ?? (() => ({})) }),
        'utils/filter-annotations': { filterAnnotations: (states) => states },
        'utils/get-hidden-z-layers': { __esModule: true, default: () => new Set() },
        reducers: { isMultiSelectionSupported: () => true },
        'antd/lib/message': { __esModule: true, default: { destroy() {}, success() {}, warning() {} } },
    };
}

// ---- the four entry points ---------------------------------------------------------------------------

const LABELS_LIST = 'cvat-ui/src/components/annotation-page/standard-workspace/objects-side-bar/labels-list.tsx';
const SELECTION_MENU = 'cvat-ui/src/components/annotation-page/canvas/views/canvas2d/selection-context-menu.tsx';
const OBJECT_ITEM = 'cvat-ui/src/containers/annotation-page/standard-workspace/objects-side-bar/object-item.tsx';
const AAM_SIDEBAR = 'cvat-ui/src/components/annotation-page/attribute-annotation-workspace/' +
    'attribute-annotation-sidebar/attribute-annotation-sidebar.tsx';

/** Presses the label hotkey for `label` (ctrl+1 = the first label, ctrl+2 = the second). */
function pressLabelHotkey(core, job, label, situation, beforeChange = () => {}) {
    const saved = [];
    const appStore = store(job, situation);
    const { default: LabelsList } = loadSource(LABELS_LIST, siteBoundaries(core, appStore, saved));
    const hotkeys = findElement(LabelsList({}), (element) => element.type === 'GlobalHotKeys', 'GlobalHotKeys');
    beforeChange();
    hotkeys.props.handlers[`SWITCH_LABEL_${LABELS.indexOf(label) + 1}`]({ preventDefault() {} });
    return saved;
}

/** Picks `label` in the label selector of the selection's context menu. */
function pickInSelectionMenu(core, job, label, situation) {
    const saved = [];
    const appStore = store(job, situation);
    const { default: SelectionContextMenu } = loadSource(SELECTION_MENU, {
        ...siteBoundaries(core, appStore, saved),
        'components/label-selector/label-selector': { __esModule: true, default: 'LabelSelector' },
    });
    const selector = findElement(
        SelectionContextMenu(), (element) => element.type === 'LabelSelector', 'LabelSelector',
    );
    selector.props.onChange(label);
    return saved;
}

/** Picks `label` in the object's sidebar item. */
function pickInSidebarItem(core, job, label, state, beforeChange = () => {}) {
    const saved = [];
    const appStore = store(job, { states: [state] });
    const { default: ObjectItem } = loadSource(OBJECT_ITEM, siteBoundaries(core, appStore, saved));
    const item = new ObjectItem({
        objectState: state,
        labels: LABELS,
        jobInstance: job,
        updateState: (updated) => saved.push({ batch: false, labels: [updated.label.id] }),
    });
    const rendered = item.render();
    const view = findElement(rendered, (element) => typeof element.props.changeLabel === 'function', 'item view');
    beforeChange();
    view.props.changeLabel(label);
    return saved;
}

/** Picks `label` for the activated object in the attribute annotation sidebar. */
function pickInAttributeAnnotation(core, job, label, state) {
    const saved = [];
    const appStore = store(job, { states: [state], activated: state.clientID });
    const { default: Sidebar } = loadSource(AAM_SIDEBAR, siteBoundaries(core, appStore, saved));
    const rendered = Sidebar({
        labels: LABELS,
        states: [state],
        activatedStateID: state.clientID,
        activatedAttributeID: null,
        keyMap: {},
        normalizedKeyMap: {},
        canvasIsReady: false,
        hiddenZLayers: new Set(),
        jobInstance: job,
        updateAnnotations: (states) => saved.push({ batch: false, labels: states.map((s) => s.label.id) }),
        changeFrame() {},
        activateObject() {},
    });
    const editor = findElement(rendered, (element) => typeof element.props.changeLabel === 'function', 'editor');
    editor.props.changeLabel(label);
    return saved;
}

function classChanges(events) {
    return events.filter((event) => event.scope === 'debug:info' && event.obj_name === RECORD);
}

// ---- tests -------------------------------------------------------------------------------------------

test('changing a box\'s label in its sidebar item sends one class change of one box, by mouse', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const saved = pickInSidebarItem(core, job, BUS, labelled({ clientID: 3 }));

    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }], 'the label change is saved as before');
    const events = await core.sent();
    const [record] = classChanges(events);
    assert.equal(classChanges(events).length, 1);
    assert.equal(record.count, 1);
    assert.equal(record.job_id, 13);
    assert.equal(record.task_id, 12);
    assert.equal(record.project_id, 11);
    assert.equal(record.payload.shape_type, 'rectangle');
    assert.equal(record.payload.rectangle_count, 1);
    assert.equal(record.payload.object_type, 'shape');
    assert.equal(record.payload.input_method, 'mouse');
    assert.equal(record.payload.client_id, core.logger.clientID);
});

test('a label hotkey on the activated object sends a class change by hotkey', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const track = labelled({ clientID: 4, shapeType: 'polygon', objectType: 'track' });
    const saved = pressLabelHotkey(core, job, BUS, { states: [track], activated: 4 });

    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);
    const [record] = classChanges(await core.sent());
    assert.equal(record.count, 1);
    assert.equal(record.payload.shape_type, 'polygon');
    assert.equal(record.payload.object_type, 'track');
    assert.equal(record.payload.rectangle_count, 0);
    assert.equal(record.payload.input_method, 'hotkey');
});

test('a label hotkey on a selection counts each object whose label changes', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const states = [
        labelled({ clientID: 1 }),
        labelled({ clientID: 2, shapeType: 'polygon' }),
        labelled({ clientID: 3, label: BUS }), // already a bus: not a class change
        labelled({ clientID: 4 }),
    ];
    const saved = pressLabelHotkey(core, job, BUS, { states, selected: [1, 2, 3, 4] });

    assert.deepEqual(saved, [{ batch: true, labels: [BUS.id, BUS.id, BUS.id] }]);
    const records = classChanges(await core.sent());
    assert.equal(records.length, 1);
    assert.equal(records[0].count, 3);
    assert.equal(records[0].payload.shape_type, 'mixed');
    assert.equal(records[0].payload.rectangle_count, 2);
    assert.equal(records[0].payload.object_type, 'shape');
    assert.equal(records[0].payload.input_method, 'hotkey');
});

test('a label picked for a selection in its context menu counts only the objects whose label changed', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const states = [
        labelled({ clientID: 1 }),
        labelled({ clientID: 2, label: BUS }),
        labelled({ clientID: 3 }),
    ];
    const saved = pickInSelectionMenu(core, job, BUS, { states, selected: [1, 2, 3] });

    assert.deepEqual(saved, [{ batch: true, labels: [BUS.id, BUS.id, BUS.id] }], 'saved as before');
    const records = classChanges(await core.sent());
    assert.equal(records.length, 1);
    assert.equal(records[0].count, 2);
    assert.equal(records[0].payload.rectangle_count, 2);
    assert.equal(records[0].payload.input_method, 'mouse');
});

test('changing the label in the attribute annotation sidebar is a class change', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const saved = pickInAttributeAnnotation(core, job, BUS, labelled({ clientID: 6 }));

    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);
    const [record] = classChanges(await core.sent());
    assert.equal(record.count, 1);
    assert.equal(record.payload.input_method, 'mouse');
});

test('picking the label an object already has sends nothing', async () => {
    const core = coreLogger();
    const job = openJob(core);
    pickInSidebarItem(core, job, CAR, labelled({ clientID: 3 }));
    pressLabelHotkey(core, job, CAR, { states: [labelled({ clientID: 4 })], activated: 4 });
    pickInSelectionMenu(core, job, CAR, { states: [labelled({ clientID: 1 }), labelled({ clientID: 2 })], selected: [1, 2] });

    assert.deepEqual(classChanges(await core.sent()), []);
});

test('changing a class back counts again', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const state = labelled({ clientID: 3 });
    pickInSidebarItem(core, job, BUS, state);
    pickInSidebarItem(core, job, CAR, state);

    assert.deepEqual(classChanges(await core.sent()).map((record) => record.count), [1, 1]);
});

test('a label hotkey with nothing selected or activated changes the default label and is no class change', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const saved = pressLabelHotkey(core, job, BUS, { states: [labelled({ clientID: 1 })] });

    assert.deepEqual(saved, []);
    assert.deepEqual(classChanges(await core.sent()), []);
});

test('a label hotkey on a locked activated object sends nothing (CVAT keeps its label)', async () => {
    const core = coreLogger();
    const job = openJob(core);
    pressLabelHotkey(core, job, BUS, { states: [labelled({ clientID: 4, lock: true })], activated: 4 });

    assert.deepEqual(classChanges(await core.sent()), []);
});

test('an object whose label cannot be read does not stop the label change', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const state = labelled({ clientID: 6 });
    let current = CAR;
    let failNextRead = false;
    // once the hotkey is pressed, the next read of the label (the recording's) fails
    Object.defineProperty(state, 'label', {
        get() {
            if (failNextRead) { failNextRead = false; throw new Error('cannot read label'); }
            return current;
        },
        set(value) { current = value; },
    });
    let saved;
    assert.doesNotThrow(() => {
        saved = pressLabelHotkey(core, job, BUS, { states: [state], activated: 6 }, () => { failNextRead = true; });
    });

    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);
    assert.deepEqual(classChanges(await core.sent()), []);
});

test('nothing is recorded in a 3D job, and the label still changes', async () => {
    const core = coreLogger();
    const job = openJob(core, { dimension: '3d' });
    const saved = pickInSidebarItem(core, job, BUS, labelled({ clientID: 3, shapeType: 'cuboid' }));

    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);
    assert.deepEqual(classChanges(await core.sent()), []);
});

test('a failure inside the recording never affects the label change', async () => {
    const core = coreLogger();
    const job = openJob(core);
    const state = labelled({ clientID: 3 });
    // once the item is shown, the logging cannot read the object's kind
    const unreadable = () => Object.defineProperty(state, 'shapeType', {
        get() { throw new Error('cannot read shapeType'); },
    });
    let saved;
    assert.doesNotThrow(() => { saved = pickInSidebarItem(core, job, BUS, state, unreadable); });
    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);

    // the logger itself refuses the record
    const refusing = { ...job, logger: { log: () => Promise.reject(new Error('refused')) } };
    assert.doesNotThrow(() => { saved = pressLabelHotkey(core, refusing, BUS, { states: [labelled({ clientID: 4 })], activated: 4 }); });
    assert.deepEqual(saved, [{ batch: false, labels: [BUS.id] }]);
    await new Promise((resolve) => setImmediate(resolve));
});

test('a class change goes to the server under a scope it accepts', async () => {
    const core = coreLogger();
    const job = openJob(core);
    pickInSelectionMenu(core, job, BUS, { states: [labelled({ clientID: 1 }), labelled({ clientID: 2 })], selected: [1, 2] });

    const events = await core.sent();
    assert.ok(events.length > 0);
    for (const event of events) assert.ok(ALLOWED_SCOPES.has(event.scope), event.scope);
});
