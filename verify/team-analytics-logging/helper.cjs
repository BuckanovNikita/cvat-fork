// Shared helper for seam 2 (the events the UI logging sends, at the boundary to the server).
//
// The real cvat-core logger (cvat-core/src/logger.ts and event.ts) collects the events; only its
// transport (`./server-proxy`) is replaced, so a test reads the batch exactly as it would be POSTed
// to /api/events. UI sources (call sites in annotation-actions.ts, canvas-wrapper.tsx, ...) are
// transpiled without type checking and evaluated the way verify/task_progress.cjs does. Imports:
//   - a boundary the test names wins;
//   - relative imports and the logging module (`utils/team-analytics-logging...`) load for real;
//   - every other path alias of the UI build (`reducers`, `actions/...`, `cvat-canvas-wrapper`, ...)
//     and any package that does not load under node becomes an inert stub (any property, call or
//     `new` gives another stub), so a call site loads without the rest of the UI.
const { readFileSync, existsSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');

const cvatRoot = path.resolve(__dirname, '../..');
const uiSrc = path.join(cvatRoot, 'cvat-ui/src');
const dependency = createRequire(path.join(cvatRoot, 'package.json'));
const ts = dependency('typescript');
// jsdom is the harness's own dependency (../browser-environment.cjs): when it does not load, this file
// fails to load and the suite with it. No test is skipped for want of a DOM.
const { JSDOM } = require('../browser-environment.cjs');

// Path aliases of the UI build that load for real (the logging module and its parts).
const REAL_ALIASES = ['utils/team-analytics-logging'];

// Client scopes the stock server (cvat/server:v2.82.0, apps/events/serializers.py ALLOWED_SCOPES) accepts.
// One scope outside this list makes the server reject the whole batch (ADR 0002).
const ALLOWED_SCOPES = new Set([
    'load:cvat', 'load:job', 'save:job', 'load:workspace', 'send:exception', 'join:objects', 'change:frame',
    'draw:object', 'paste:object', 'copy:object', 'propagate:object', 'drag:object', 'resize:object',
    'delete:object', 'merge:objects', 'split:objects', 'group:objects', 'slice:object', 'zoom:image',
    'fit:image', 'rotate:image', 'action:undo', 'action:redo', 'debug:info', 'run:annotations_action',
    'click:element', 'user:activity',
]);

/** An inert stand-in: any property, call or construction gives another stub; it is never a promise. */
function stub(label = 'stub') {
    const target = function stubbed() {};
    return new Proxy(target, {
        get(_target, property) {
            if (property === 'then') return undefined;
            if (property === '__esModule') return true;
            if (property === Symbol.toPrimitive) return () => label;
            if (property === 'prototype') return target.prototype;
            if (typeof property === 'symbol') return undefined;
            return stub(`${label}.${String(property)}`);
        },
        apply() { return stub(`${label}()`); },
        construct() { return stub(`new ${label}`); },
    });
}

/** `object`, with a stub for every property it lacks. */
function withStubs(object, label = 'stub') {
    return new Proxy(object, {
        get(target, property, receiver) {
            if (property in target || typeof property === 'symbol' || property === 'then') {
                return Reflect.get(target, property, receiver);
            }
            return stub(`${label}.${String(property)}`);
        },
    });
}

function existing(base) {
    return [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')]
        .find((candidate) => existsSync(candidate) && !candidate.endsWith(path.sep) &&
            !require('node:fs').statSync(candidate).isDirectory());
}

/**
 * Loads a source file; `relativePath` is relative to the repository root (e.g. 'cvat-ui/src/actions/annotation-actions.ts').
 * `boundaries` maps import specifiers to replacements. Every call evaluates fresh module instances.
 */
function loadSource(relativePath, boundaries = {}, warnings = []) {
    const cache = new Map();
    function load(filename) {
        if (cache.has(filename)) return cache.get(filename).exports;
        const { outputText } = ts.transpileModule(readFileSync(filename, 'utf8'), {
            fileName: filename,
            compilerOptions: {
                module: ts.ModuleKind.CommonJS,
                target: ts.ScriptTarget.ES2020,
                jsx: ts.JsxEmit.React,
                esModuleInterop: true,
            },
        });
        const loaded = { exports: {} };
        cache.set(filename, loaded);
        const resolve = (name) => {
            if (Object.hasOwn(boundaries, name)) return boundaries[name];
            if (name.endsWith('.scss') || name.endsWith('.css') || name.endsWith('.svg')) return {};
            if (name.startsWith('.')) {
                const target = existing(path.resolve(path.dirname(filename), name));
                if (!target) throw new Error(`cannot resolve ${name} from ${filename}`);
                return load(target);
            }
            const alias = existing(path.join(uiSrc, name));
            if (alias) {
                return REAL_ALIASES.some((real) => name === real || name.startsWith(`${real}/`)) ?
                    load(alias) : stub(name);
            }
            try {
                return dependency(name);
            } catch {
                return stub(name);
            }
        };
        const evaluate = new Function('require', 'module', 'exports', 'console', outputText);
        evaluate(resolve, loaded, loaded.exports, { ...console, warn: (...args) => warnings.push(args) });
        return loaded.exports;
    }
    return load(path.join(cvatRoot, relativePath));
}

/**
 * The real cvat-core logger with a recording transport. `sent()` flushes it (as the UI's timer does)
 * and returns every event POSTed so far, with `payload` parsed. `failSaves` makes the server answer
 * with an error.
 */
function coreLogger() {
    const posts = [];
    const transport = {
        failSaves: false,
        events: {
            async save(body) {
                if (transport.failSaves) throw new Error('server unavailable');
                posts.push(JSON.parse(JSON.stringify(body)));
            },
        },
        server: { getAndResetBandwidthInfo: () => ({}) },
    };
    const enums = loadSource('cvat-core/src/enums.ts');
    const { default: logger } = loadSource('cvat-core/src/logger.ts', { './server-proxy': transport });
    return {
        logger,
        enums,
        transport,
        posts,
        async sent() {
            await logger.save();
            return posts.flatMap((body) => body.events).map((event) => ({
                ...event,
                payload: event.payload ? JSON.parse(event.payload) : {},
            }));
        },
    };
}

/**
 * An open job as the UI holds it: its logger adds the job's identifiers the way
 * cvat-core/src/session-implementation.ts does (spread after the caller's payload).
 */
function openJob(core, {
    dimension = '2d', projectId = 11, taskId = 12, id = 13,
} = {}) {
    return {
        id,
        projectId,
        taskId,
        dimension,
        logger: {
            log: (scope, payload = {}, wait = false) => core.logger.log(scope, {
                ...payload, project_id: projectId, task_id: taskId, job_id: id,
            }, wait),
        },
    };
}

/** Boundaries every UI call site needs: cvat-core (real enums, `getCore()` with the real logger) and cvat-logger. */
function uiBoundaries(core, coreParts = {}) {
    return {
        'cvat-core-wrapper': withStubs({
            ...core.enums,
            getCore: () => withStubs({ logger: core.logger, ...coreParts }, 'core'),
        }, 'cvat-core-wrapper'),
        'cvat-logger': { __esModule: true, default: core.logger, EventScope: core.enums.EventScope },
    };
}

/** A plain object state as the UI passes it around (ObjectState fields the logging reads). */
function objectState(fields = {}) {
    return {
        clientID: 1, serverID: undefined, shapeType: 'rectangle', objectType: 'shape', frame: 0, ...fields,
    };
}

const CANVAS_WRAPPER = 'cvat-ui/src/components/annotation-page/canvas/views/canvas2d/canvas-wrapper.tsx';
const ANNOTATION_ACTIONS = 'cvat-ui/src/actions/annotation-actions.ts';

// cvat-core's ObjectState as the call sites construct it: the serialized fields, as given.
class FakeObjectState {
    constructor(serialized) { Object.assign(this, serialized); }
}

// The 2D canvas: a paste placement finishes as soon as it starts, at no offset.
class FakeCanvas {
    cancel() {}

    draw({ onDrawDone }) { onDrawDone({ offset: { x: 0, y: 0 } }); }
}

/**
 * The 2D canvas wrapper component (canvas-wrapper.tsx) with `props` for `job`. Call its handlers
 * (`onCanvasShapeDrawn`, `onCanvasShapeDragged`, ...) with canvas events; `created` collects created objects.
 */
function canvasWrapper(core, job, props = {}, boundaries = {}) {
    const module = loadSource(CANVAS_WRAPPER, {
        ...uiBoundaries(core, { classes: { ObjectState: FakeObjectState } }), ...boundaries,
    });
    const Component = module.default.WrappedComponent;
    const created = [];
    const component = new Component({
        jobInstance: job,
        activeLabelID: 1,
        activeObjectType: 'shape',
        frame: 4,
        currentZLayer: 0,
        activeObjectHidden: false,
        workspace: 'Standard',
        updateActiveControl() {},
        onCreateAnnotations(states) { created.push(...states); },
        onUpdateEditedObject() {},
        ...props,
    });
    return { component, created };
}

/**
 * The annotation actions (annotation-actions.ts) over a store whose `annotation` state holds `job`, the
 * object `states`, the selection, the activated object and the copied states. `dispatch` runs thunks and
 * records plain actions in `dispatched`. `coreParts` adds to what `getCore()` returns (e.g. `utils`).
 */
function annotationActions(core, job, {
    states = [], selected = [], activated = null, copied = [],
} = {}, coreParts = {}, boundaries = {}) {
    const store = {
        getState: () => ({
            annotation: {
                annotations: {
                    states, selectedStatesID: selected, activatedStateID: activated, filters: [], zLayer: { cur: 0 },
                },
                player: { frame: { number: 4 } },
                job: {
                    instance: job,
                    frameNumbers: [0, 1, 2, 3, 4, 5, 6, 7],
                    groundTruthInfo: { groundTruthInstance: null, validationLayout: null },
                },
                workspace: 'Standard',
                drawing: { copiedStates: copied },
                canvas: { instance: new FakeCanvas() },
            },
            settings: { workspace: { showAllInterpolationTracks: false }, shapes: { showGroundTruth: false } },
        }),
    };
    const actions = loadSource(ANNOTATION_ACTIONS, {
        ...uiBoundaries(core, { classes: { ObjectState: FakeObjectState }, ...coreParts }),
        'cvat-store': { getCVATStore: () => store },
        'cvat-canvas-wrapper': withStubs({ Canvas: FakeCanvas }, 'cvat-canvas-wrapper'),
        ...boundaries,
    });
    const dispatched = [];
    const dispatch = (action) => {
        if (typeof action === 'function') return action(dispatch, store.getState);
        dispatched.push(action);
        return action;
    };
    return { actions, dispatch, dispatched };
}

/** A jsdom window (no Node globals are set). */
function domWindow(html = '<!doctype html><html><body></body></html>') {
    return new JSDOM(html, { url: 'http://localhost/tasks/12/jobs/13' }).window;
}

/** The one event of`scope` among `events` (fails otherwise). */
function only(events, scope) {
    const assert = require('node:assert/strict');
    const matching = events.filter((event) => event.scope === scope);
    assert.equal(matching.length, 1, `one ${scope} event, got ${JSON.stringify(events)}`);
    return matching[0];
}

module.exports = {
    ALLOWED_SCOPES,
    annotationActions,
    canvasWrapper,
    coreLogger,
    dependency,
    domWindow,
    loadSource,
    objectState,
    only,
    openJob,
    stub,
    uiBoundaries,
    withStubs,
};
