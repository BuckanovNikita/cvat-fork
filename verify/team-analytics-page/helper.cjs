// Shared helper for seam 3 (the Team Analytics page with supplied service responses).
// Loads the fork's TypeScript/React sources from cvat/cvat-ui/src/components/team-analytics-page/
// the way verify/task_progress.cjs does: transpile without type checking, evaluate, and replace
// only the boundaries a test names. Relative imports between page files resolve automatically,
// so a new card file needs no change here; stylesheets load as empty modules.
const { readFileSync, existsSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');

const cvatRoot = path.resolve(__dirname, '../../cvat');
const pageDir = path.join(cvatRoot, 'cvat-ui/src/components/team-analytics-page');
const dependency = createRequire(path.join(cvatRoot, 'package.json'));
const ts = dependency('typescript');

// jsdom (locked in cvat/yarn.lock as an optional dependency of fabric) must exist before react-dom
// is first loaded, so that the client renderer sees a DOM. Tests that mount check `domAvailable`.
// jsdom probes the optional native `canvas` package, whose binary is not built here: hide it.
function loadJsdom() {
    const Module = require('node:module');
    const resolveFilename = Module._resolveFilename;
    Module._resolveFilename = function resolve(request, ...rest) {
        if (request === 'canvas') {
            throw Object.assign(new Error("Cannot find module 'canvas'"), { code: 'MODULE_NOT_FOUND' });
        }
        return resolveFilename.call(this, request, ...rest);
    };
    try {
        return dependency('jsdom');
    } catch {
        return null;
    } finally {
        Module._resolveFilename = resolveFilename;
    }
}
const jsdom = loadJsdom();
const domAvailable = !!jsdom;
if (jsdom) {
    const dom = new jsdom.JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/team-analytics' });
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
}

const React = dependency('react');
const { renderToStaticMarkup } = dependency('react-dom/server');
const { createRoot } = dependency('react-dom/client');
const { act } = dependency('react-dom/test-utils');

function resolveRelative(fromFile, specifier) {
    const base = path.resolve(path.dirname(fromFile), specifier);
    const candidates = [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')];
    return candidates.find((candidate) => existsSync(candidate) && !candidate.endsWith(path.sep));
}

/**
 * Loads a page source file. `relativePath` is relative to the page directory
 * (e.g. 'team-analytics-view.tsx'). `boundaries` maps import specifiers to replacements.
 */
function loadPage(relativePath, boundaries = {}, warnings = []) {
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
            if (name === 'cvat-core-wrapper') return { getCore() { throw new Error('cvat-core is not loaded in seam 3'); } };
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
            }
        },
        async unmount() {
            await act(async () => { root.unmount(); });
            container.remove();
        },
    };
}

/** A fetch replacement answering with supplied service responses; records the requests. */
function suppliedFetch(answer) {
    const requests = [];
    const fetch = async (url, init = {}) => {
        requests.push({ url: String(url), init });
        const response = await answer(String(url), init);
        if (response instanceof Error) throw response;
        const { status = 200, body = {} } = response;
        return {
            ok: status >= 200 && status < 300,
            status,
            json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
        };
    };
    return { fetch, requests };
}

module.exports = {
    React, act, dependency, domAvailable, loadPage, mount, render, suppliedFetch, text,
};
