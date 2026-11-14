// Review of 2026-11-15, finding 2: the window listeners the counting needs are attached by the
// application itself. The real application component (components/cvat-app.tsx) mounts over a jsdom
// window, with the rest of the UI left out; a key press and a click on that window then reach the
// counting, and the batch the real cvat-core logger sends comes out.
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    coreLogger, dependency, domWindow, loadSource, openJob, stub, uiBoundaries, withStubs,
} = require('./helper.cjs');

const React = dependency('react');
const LOGGING = 'utils/team-analytics-logging';
const SUMMARY = 'team_analytics:input_summary';

const PAGE = `<!doctype html><html><body>
  <div class="cvat-annotation-header"><button id="save">Save</button></div>
</body></html>`;

// cvat-app.tsx's own relative imports: pages and dialogs the mount does not need
const LEFT_OUT = [
    './common/cvat-markdown', './email-confirmation-pages/email-confirmed',
    './email-confirmation-pages/email-verification-sent', './email-confirmation-pages/incorrect-email-confirmation',
    './create-job-page/create-job-page', './quality-control/quality-control-page',
    './analytics-report/analytics-report-page', './consensus-management-page/consensus-management-page',
    './team-analytics-page/team-analytics-route', './invitation-watcher/invitation-watcher',
    './select-organization-modal/select-organization-modal', './bulk-progress',
];

function mountedApplication() {
    const core = coreLogger();
    const logging = loadSource('cvat-ui/src/utils/team-analytics-logging/index.ts', uiBoundaries(core));
    const boundaries = {
        ...Object.fromEntries(LEFT_OUT.map((name) => [name, stub(name)])),
        react: { __esModule: true, ...React, default: React },
        'react-router-dom': withStubs({ __esModule: true, withRouter: (component) => component }, 'react-router-dom'),
        'cvat-core-wrapper': withStubs({
            getCore: () => ({
                logger: { configure() {} },
                config: {},
                // the server never answers: the mount does not wait for it
                server: { healthCheck: () => new Promise(() => {}) },
            }),
        }, 'cvat-core-wrapper'),
        'utils/platform-checker': {
            __esModule: true,
            default: () => false,
            platformInfo: () => ({}),
            stopNotifications() {},
            showUnsupportedNotification: () => false,
        },
        [LOGGING]: logging,
    };
    const { default: CVATApplication } = loadSource('cvat-ui/src/components/cvat-app.tsx', boundaries);
    const application = new CVATApplication({ history: { listen() {} }, onChangeLocation() {} });

    const window = domWindow(PAGE);
    const previous = Object.getOwnPropertyDescriptor(globalThis, 'window');
    globalThis.window = window;
    try {
        application.componentDidMount();
    } finally {
        if (previous) Object.defineProperty(globalThis, 'window', previous);
        else delete globalThis.window;
    }
    return { core, logging, window };
}

test('the application attaches the listeners the counting needs: a key press and a click reach it', async (t) => {
    t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-15T10:00:00Z') });
    const { core, logging, window } = mountedApplication();
    logging.trackInputJob(openJob(core));
    window.document.getElementById('save').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    t.mock.timers.tick(2 * 60_000);
    // a key press after a minute: the summary of the click is written then
    window.document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'a', bubbles: true }));

    const summaries = (await core.sent()).filter((event) => event.obj_name === SUMMARY);
    assert.equal(summaries.length, 1);
    assert.deepEqual(summaries[0].payload.mouse, { header: 1 });
});
