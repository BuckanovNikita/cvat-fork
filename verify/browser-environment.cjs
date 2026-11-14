// The browser environment of the frontend suites (seams 2 and 3): jsdom, declared in verify/package.json
// and installed into verify/node_modules with `npm ci --prefix verify`. It resolves from that manifest,
// not from the import's dependencies. A suite that cannot load it fails here, naming what is missing,
// instead of skipping the tests that need a DOM.
const { createRequire } = require('node:module');
const path = require('node:path');

const harnessDependency = createRequire(path.join(__dirname, 'package.json'));

function loadJsdom() {
    try {
        return harnessDependency('jsdom');
    } catch (cause) {
        const [reason] = String(cause.message).split('\n');
        throw new Error(
            'jsdom, the browser environment of the frontend suites, did not load from verify/node_modules: ' +
            `${reason}. Install the harness's dependencies: npm ci --prefix verify`,
            { cause },
        );
    }
}

module.exports = loadJsdom();
