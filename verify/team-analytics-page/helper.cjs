// Shared helper for seam 3 (the Team Analytics page with supplied service responses).
// Loads the fork's TypeScript/React sources from cvat-ui/src/components/team-analytics-page/
// the way verify/task_progress.cjs does: transpile without type checking, evaluate, and replace
// only the boundaries a test names. Relative imports between page files resolve automatically,
// so a new card file needs no change here; stylesheets load as empty modules.
const { readFileSync, existsSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');

const cvatRoot = path.resolve(__dirname, '../..');
const pageDir = path.join(cvatRoot, 'cvat-ui/src/components/team-analytics-page');
const dependency = createRequire(path.join(cvatRoot, 'package.json'));
const ts = dependency('typescript');

// jsdom must exist before react-dom is first loaded, so that the client renderer sees a DOM. It is the
// harness's own dependency (../browser-environment.cjs): when it does not load, this file fails to load
// and the suite with it. No test is skipped for want of a DOM.
const { JSDOM } = require('../browser-environment.cjs');

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/team-analytics' });
dom.window.matchMedia = dom.window.matchMedia || (() => ({
    matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
}));
// Expose the DOM API (window, document, ShadowRoot, ...) as Node globals, keeping Node's own.
for (const key of Object.getOwnPropertyNames(dom.window)) {
    if (!(key in globalThis) && !key.startsWith('_')) {
        Object.defineProperty(globalThis, key, { configurable: true, writable: true, value: dom.window[key] });
    }
}
for (const key of ['window', 'document', 'navigator']) {
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value: dom.window[key] });
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// --- guards: a runaway test ends as a failed test, not as a process that grows without end ---------------------

// A failed comparison of node:assert describes its values in full, following every property. A mounted page
// element carries React's whole component tree in its own properties, so a failed `assert.equal(element, null)`
// grew the test process past 3 GB in seconds (on 2026-11-16 one grew to 49.5 GB and hung the machine). The
// comparisons of `node:assert/strict` therefore see a DOM node as a short description, `<div class="...">`; equal
// and notEqual still compare identity, the deep comparisons compare the descriptions.
const strictAssert = require('node:assert/strict');

function isDomNode(value) {
    return value instanceof dom.window.Node;
}

function describeNode(node) {
    if (node.nodeType !== dom.window.Node.ELEMENT_NODE) return `#${node.nodeName.replace(/^#/, '')}`;
    const className = node.getAttribute('class');
    return `<${node.localName}${className ? ` class="${className}"` : ''}>`;
}

function withoutNodes(value, seen = new Map()) {
    if (isDomNode(value)) return describeNode(value);
    if (!value || typeof value !== 'object' || !(Array.isArray(value) || Object.getPrototypeOf(value) === Object.prototype)) {
        return value;
    }
    if (seen.has(value)) return seen.get(value);
    const copy = Array.isArray(value) ? [] : {};
    seen.set(value, copy);
    for (const key of Object.keys(value)) copy[key] = withoutNodes(value[key], seen);
    return copy;
}

function containsNode(value, seen = new Set()) {
    if (isDomNode(value)) return true;
    if (!value || typeof value !== 'object' || seen.has(value) ||
        !(Array.isArray(value) || Object.getPrototypeOf(value) === Object.prototype)) return false;
    seen.add(value);
    return Object.keys(value).some((key) => containsNode(value[key], seen));
}

for (const [name, same] of [['equal', true], ['strictEqual', true], ['notEqual', false], ['notStrictEqual', false]]) {
    const original = strictAssert[name];
    strictAssert[name] = function comparedWithoutNodes(actual, expected, message) {
        if (!isDomNode(actual) && !isDomNode(expected)) return original(actual, expected, message);
        if (Object.is(actual, expected) === same) return undefined;
        if (message instanceof Error) throw message;
        throw new strictAssert.AssertionError({
            actual: withoutNodes(actual),
            expected: withoutNodes(expected),
            operator: same ? 'strictEqual' : 'notStrictEqual',
            message: message ?? `${withoutNodes(actual)} ${same ? 'is not' : 'is'} ${withoutNodes(expected)}`,
            stackStartFn: comparedWithoutNodes,
        });
    };
}
for (const name of ['deepEqual', 'deepStrictEqual', 'notDeepEqual', 'notDeepStrictEqual']) {
    const original = strictAssert[name];
    strictAssert[name] = function comparedWithoutNodes(actual, expected, message) {
        if (!containsNode(actual) && !containsNode(expected)) return original(actual, expected, message);
        return original(withoutNodes(actual), withoutNodes(expected), message);
    };
}

// The request stand-ins below count the requests of the running test. A page that asks again and again
// (an effect that re-runs on its own answer) fails its test at the limit, naming the endpoint, instead of
// growing; the request over the limit is never answered, which stops a loop driven by the answers.
const REQUEST_LIMIT = 300;
const sent = { count: 0, runaway: null };

function counted(endpoint) {
    sent.count += 1;
    if (sent.count <= REQUEST_LIMIT) return true;
    if (!sent.runaway) {
        sent.runaway = new Error(`the test made more than ${REQUEST_LIMIT} requests (the last: ${endpoint}): the ` +
            'page repeats a request without end');
        // said at once too: a test that awaits the unanswered request itself ends without its after-each hook
        console.error(sent.runaway.message);
    }
    return false;
}

function failOnRunaway() {
    if (sent.runaway) throw sent.runaway;
}

const nodeTest = require('node:test');

nodeTest.beforeEach(() => {
    sent.count = 0;
    sent.runaway = null;
});
nodeTest.afterEach(failOnRunaway);

// antd 5.17's CommonJS build has one stray ES-module import, `rc-util/es/ref` in lib/_util/wave/WaveEffect.js (used by
// Button, hence Modal), which the UI's bundler resolves and Node cannot load. Here it gets rc-util's CommonJS twin.
const Module = require('node:module');

const resolveFilename = Module._resolveFilename;
Module._resolveFilename = function resolveCommonJsTwin(request, ...rest) {
    return resolveFilename.call(this, request.replace(/^rc-util\/es\//, 'rc-util/lib/'), ...rest);
};

const React = dependency('react');
const { renderToStaticMarkup } = dependency('react-dom/server');
const { createRoot } = dependency('react-dom/client');
const { act } = dependency('react-dom/test-utils');

function resolveRelative(fromFile, specifier) {
    const base = path.resolve(path.dirname(fromFile), specifier);
    const candidates = [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')];
    return candidates.find((candidate) => existsSync(candidate) && !candidate.endsWith(path.sep));
}

let loadedCoreExceptions = null;
function coreExceptions() {
    if (!loadedCoreExceptions) loadedCoreExceptions = loadCoreExceptions();
    return loadedCoreExceptions;
}

// The store a test supplies through 'react-redux' signs in an administrator unless it names `auth` itself:
// only administrators read Team Analytics, and most tests are about what an administrator sees.
const ADMINISTRATOR = { user: { username: 'admin', groups: ['admin'] } };

function withAdministrator(boundaries) {
    const redux = boundaries['react-redux'];
    if (!redux?.useSelector) return boundaries;
    const useSelector = (select) => redux.useSelector((state) => select(
        state && typeof state === 'object' && !('auth' in state) ? { ...state, auth: ADMINISTRATOR } : state,
    ));
    return { ...boundaries, 'react-redux': { ...redux, useSelector } };
}

/**
 * Loads a page source file. `relativePath` is relative to the page directory
 * (e.g. 'team-analytics-view.tsx'). `boundaries` maps import specifiers to replacements.
 */
function loadPage(relativePath, suppliedBoundaries = {}, warnings = []) {
    const boundaries = withAdministrator(suppliedBoundaries);
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
            if (name.endsWith('.scss') || name.endsWith('.css')) return {};
            // the CVAT client (a path alias of the UI build) is not loaded here: a page call into it fails,
            // as an unreachable CVAT would; tests that need its answers supply the page module using it
            if (name === 'cvat-core-wrapper') {
                return {
                    getCore() { throw new Error('cvat-core is not loaded in seam 3'); },
                    ServerError: coreExceptions().ServerError,
                };
            }
            if (name.startsWith('.')) {
                const target = resolveRelative(filename, name);
                if (!target) throw new Error(`cannot resolve ${name} from ${filename}`);
                return load(target);
            }
            return dependency(name);
        };
        const evaluate = new Function('require', 'module', 'exports', 'console', outputText);
        evaluate(resolve, loaded, loaded.exports, { ...console, warn: (...args) => warnings.push(args) });
        return loaded.exports;
    }
    return load(path.join(pageDir, relativePath));
}

function render(Component, props = {}) {
    // With a jsdom window present antd picks useLayoutEffect, which React reports on the server.
    const originalError = console.error;
    console.error = (message, ...rest) => {
        if (!String(message).includes('useLayoutEffect does nothing on the server')) originalError(message, ...rest);
    };
    try {
        return renderToStaticMarkup(React.createElement(Component, props));
    } finally {
        console.error = originalError;
    }
}

/** Text content of static markup, tags removed and whitespace collapsed. */
function text(html) {
    return html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&')
        .replace(/\s+/g, ' ').trim();
}

/** Mounts an element into the jsdom document; returns { container, unmount }. */
async function mount(element) {
    const container = document.createElement('div');
    document.body.append(container);
    const root = createRoot(container);
    await act(async () => { root.render(element); });
    return {
        container,
        async settle() {
            for (let i = 0; i < 5; i += 1) {
                // eslint-disable-next-line no-await-in-loop
                await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
                failOnRunaway();
            }
        },
        async unmount() {
            await act(async () => { root.unmount(); });
            container.remove();
        },
    };
}

/**
 * A replacement of the page's boundary (`requestService(endpoint, params)` in service.ts) answering with
 * supplied API answers; records the requests. `answer(url, request)` receives the address the request names,
 * `/api/team-analytics/<endpoint>?<params>`, and returns `{ status, body }` or an Error (no answer at all).
 * A string body is parsed as JSON when it is JSON and kept as text otherwise, as Axios does.
 */
function suppliedService(answer) {
    const requests = [];
    const request = async (endpoint, params = {}) => {
        const url = `/api/team-analytics/${endpoint}?${new URLSearchParams(params)}`;
        const record = { endpoint, params: { ...params }, url };
        requests.push(record);
        if (!counted(endpoint)) return new Promise(() => {});
        const response = await answer(url, record);
        if (response instanceof Error) throw response;
        const { status = 200, body = {} } = response;
        if (typeof body !== 'string') return { status, body };
        try {
            return { status, body: JSON.parse(body) };
        } catch {
            return { status, body };
        }
    };
    return { request, requests };
}

/**
 * A replacement of the settings boundary (`requestSettings(method, body)` in service.ts) answering with supplied
 * API answers; records each request's method and a copy of its body. `answer(request)` returns
 * `{ status, body, message }` (message: the text cvat-core made of an error body) or an Error (no answer at all).
 */
function suppliedSettings(answer) {
    const requests = [];
    const request = async (method, body) => {
        const record = { method, body: body === undefined ? undefined : JSON.parse(JSON.stringify(body)) };
        requests.push(record);
        if (!counted(`settings (${method})`)) return new Promise(() => {});
        const response = await answer(record);
        if (response instanceof Error) throw response;
        const { status = 200, body: answered = {}, message } = response;
        return { status, body: answered, message };
    };
    return { request, requests };
}

/** cvat-core's own exception classes (cvat-core/src/exceptions.ts), transpiled like the page sources. */
function loadCoreExceptions() {
    const filename = path.join(cvatRoot, 'cvat-core/src/exceptions.ts');
    const coreDependency = createRequire(filename);
    const { outputText } = ts.transpileModule(readFileSync(filename, 'utf8'), {
        fileName: filename,
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    });
    const loaded = { exports: {} };
    new Function('require', 'module', 'exports', outputText)(coreDependency, loaded, loaded.exports);
    return loaded.exports;
}

module.exports = {
    React, act, dependency, loadCoreExceptions, loadPage, mount, render, suppliedService, suppliedSettings, text,
};
