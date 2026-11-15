// The browser environment of the frontend suites (seams 2 and 3): jsdom, declared in verify/package.json
// and installed into verify/node_modules with `npm ci --prefix verify`. A suite that cannot load it fails
// here, naming what is missing, instead of skipping the tests that need a DOM.
const path = require('node:path');

// By path, not by name: by name Node would go on to parent directories and its global folders, and a
// copy found there is not the one the lock names. Upstream's dependencies are not searched either.
const installed = path.join(__dirname, 'node_modules', 'jsdom');

// jsdom draws canvases with the optional package `canvas` when Node can resolve it. Since the
// repository root became upstream's workspace root, its node_modules is on jsdom's search path and
// holds a `canvas` whose native part is not built, so jsdom would find it and fail to load. The
// harness has no canvas of its own (verify/package.json), so while jsdom loads, `canvas` is reported
// to it as not installed, which is what jsdom saw before.
function withoutCanvas(load) {
    const Module = require('node:module');
    const resolve = Module._resolveFilename;
    const ownModules = path.join(__dirname, 'node_modules') + path.sep;
    Module._resolveFilename = function resolveWithoutCanvas(request, parent, ...rest) {
        if (request === 'canvas' && parent && String(parent.filename).startsWith(ownModules)) {
            throw Object.assign(new Error("Cannot find module 'canvas'"), { code: 'MODULE_NOT_FOUND' });
        }
        return resolve.call(this, request, parent, ...rest);
    };
    try {
        return load();
    } finally {
        Module._resolveFilename = resolve;
    }
}

function loadJsdom() {
    try {
        return withoutCanvas(() => require(installed));
    } catch (cause) {
        const [reason] = String(cause.message).replace(__dirname, 'verify').split('\n');
        throw new Error(
            'jsdom, the browser environment of the frontend suites, did not load from verify/node_modules: ' +
            `${reason}. Install the harness's dependencies: npm ci --prefix verify`,
            { cause },
        );
    }
}

module.exports = loadJsdom();
