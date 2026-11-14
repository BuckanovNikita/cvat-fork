// The browser environment of the frontend suites (seams 2 and 3): jsdom, declared in verify/package.json
// and installed into verify/node_modules with `npm ci --prefix verify`. A suite that cannot load it fails
// here, naming what is missing, instead of skipping the tests that need a DOM.
const path = require('node:path');

// By path, not by name: by name Node would go on to parent directories and its global folders, and a
// copy found there is not the one the lock names. The import's dependencies are not searched either.
const installed = path.join(__dirname, 'node_modules', 'jsdom');

function loadJsdom() {
    try {
        return require(installed);
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
