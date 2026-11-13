// Run after installing cvat's dependencies: node --test verify/task_progress.cjs
// Executes the fork's TypeScript and React components; only API and unrelated
// application boundaries are mocked. No server or browser is required.
// Also check computed colors in Chrome/Chromium with BROWSER_BIN=google-chrome.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');

const cvatRoot = path.resolve(__dirname, '../cvat');
const dependency = createRequire(path.join(cvatRoot, 'package.json'));
const ts = dependency('typescript');
const React = dependency('react');
const { renderToStaticMarkup } = dependency('react-dom/server');

function loadSource(relativePath, boundaries = {}, warnings = []) {
    const filename = path.join(cvatRoot, relativePath);
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
    const resolve = (name) => (Object.hasOwn(boundaries, name) ? boundaries[name] : dependency(name));
    const evaluate = new Function('require', 'module', 'exports', 'console', outputText);
    evaluate(resolve, loaded, loaded.exports, { ...console, warn: (...args) => warnings.push(args) });
    return loaded.exports;
}

const enums = loadSource('cvat-core/src/enums.ts');
const { JobStage, JobState } = enums;
const summaryModule = loadSource('cvat-ui/src/utils/task-jobs-summary.ts', {
    'cvat-core-wrapper': enums,
});
const aggregate = summaryModule.default;
const Progress = loadSource('cvat-ui/src/components/tasks-page/task-jobs-progress.tsx', {
    'cvat-core-wrapper': enums,
    'utils/task-jobs-summary': summaryModule,
}).default;

const cases = [
    [JobStage.ANNOTATION, JobState.NEW, '#c1c1c1'],
    [JobStage.ANNOTATION, JobState.IN_PROGRESS, '#faad14'],
    [JobStage.ANNOTATION, JobState.COMPLETED, '#fafe01'],
    [JobStage.ANNOTATION, JobState.REJECTED, '#ff4136'],
    [JobStage.VALIDATION, JobState.NEW, '#b4dafd'],
    [JobStage.VALIDATION, JobState.IN_PROGRESS, '#1890ff'],
    [JobStage.VALIDATION, JobState.COMPLETED, '#00478a'],
    [JobStage.VALIDATION, JobState.REJECTED, '#ff4136'],
    [JobStage.ACCEPTANCE, JobState.NEW, '#b3ff66'],
    [JobStage.ACCEPTANCE, JobState.IN_PROGRESS, '#b3ff66'],
    [JobStage.ACCEPTANCE, JobState.COMPLETED, '#61c200'],
    [JobStage.ACCEPTANCE, JobState.REJECTED, '#ff4136'],
];

for (const [stage, state] of cases) {
    test(`preserves the independent count for ${stage}/${state}`, () => {
        const result = aggregate([{ taskId: 7, stage, state }], [7])[7];
        assert.ok(result.counts, 'expected separate counts for every stage and state');
        assert.equal(result.counts[stage][state], 1);
        assert.equal(result.fetched, 1);
        for (const [otherStage, otherState] of cases) {
            assert.equal(result.counts[otherStage][otherState], otherStage === stage && otherState === state ? 1 : 0);
        }
    });
}

test('isolates tasks, initializes missing jobs, and ignores unrelated/null task IDs', () => {
    const job = { stage: JobStage.ANNOTATION, state: JobState.NEW };
    const result = aggregate([7, 7, 8, 999, null].map((taskId) => ({ ...job, taskId })), [7, 8, 9]);
    assert.deepEqual(Object.keys(result), ['7', '8', '9']);
    assert.ok(result[7].counts, 'expected stage/state counts');
    assert.equal(result[7].counts.annotation.new, 2);
    assert.equal(result[8].counts.annotation.new, 1);
    assert.ok(Object.values(result[9].counts).flatMap(Object.values).every((count) => count === 0));
    assert.equal(result[9].fetched, 0);
    assert.deepEqual(aggregate([], []), {});
});

function harness(getJobs) {
    const calls = [];
    const warnings = [];
    const actions = loadSource('cvat-ui/src/actions/tasks-actions.ts', {
        'cvat-core-wrapper': { ...enums, getCore: () => ({ jobs: { get: getJobs } }) },
        'utils/task-jobs-summary': summaryModule,
        'utils/filter-null': loadSource('cvat-ui/src/utils/filter-null.ts'),
        'components/create-task-page/quality-configuration-form': {},
        'utils/enums': {},
        './models-actions': {},
        './requests-actions': {},
    }, warnings);
    const reducer = loadSource('cvat-ui/src/reducers/tasks-reducer.ts', {
        'actions/tasks-actions': actions,
        'actions/boundaries-actions': { BoundariesActionTypes: {} },
        'actions/auth-actions': { AuthActionTypes: {} },
        'actions/projects-actions': { ProjectsActionTypes: {} },
        'actions/selection-actions': { SelectionActionsTypes: {} },
        '.': {},
    }).default;
    let state = reducer(undefined, { type: '@@INIT' });
    const dispatch = (action) => {
        calls.push(action);
        state = reducer(state, action);
    };
    const page = (timestamp) => dispatch({
        type: actions.TasksActionTypes.GET_TASKS,
        payload: { fetchingTimestamp: timestamp, query: {}, updateQuery: true },
    });
    page(100);
    return {
        actions, calls, warnings, page,
        state: () => state,
        run: (ids, timestamp = 100) => actions.getTasksJobsSummaryAsync(ids, timestamp)(
            dispatch, () => ({ tasks: state }),
        ),
    };
}

test('fetches all page jobs and publishes summaries through the actual reducer', async () => {
    const h = harness(async (filter, allPages) => {
        assert.deepEqual(JSON.parse(filter.filter), { in: [{ var: 'task_id' }, [7, 8]] });
        assert.equal(allPages, true);
        assert.equal(h.state().jobsSummary.fetching, true);
        return [{ taskId: 7, stage: JobStage.ACCEPTANCE, state: JobState.COMPLETED }];
    });
    await h.run([7, 8]);
    assert.equal(h.state().jobsSummary.data[7].counts?.acceptance.completed, 1);
    assert.equal(h.state().jobsSummary.data[8].fetched, 0);
    assert.equal(h.state().jobsSummary.fetching, false);
    h.page(200);
    assert.deepEqual(h.state().jobsSummary, { data: {}, fetching: false });
});

test('does not request jobs for an empty task page', async () => {
    const h = harness(() => assert.fail('unexpected jobs request'));
    const count = h.calls.length;
    await h.run([]);
    assert.equal(h.calls.length, count);
});

test('API failure clears summary data to restore the stock progress fallback', async () => {
    let fail = false;
    const h = harness(async () => {
        if (fail) throw new Error('jobs unavailable');
        return [{ taskId: 7, stage: JobStage.ANNOTATION, state: JobState.NEW }];
    });
    await h.run([7]);
    assert.equal(h.state().jobsSummary.data[7].counts?.annotation.new, 1);
    fail = true;
    await h.run([7]);
    assert.deepEqual(h.state().jobsSummary, { fetching: false, data: {} });
    assert.equal(h.warnings.length, 1);
});

for (const outcome of ['success', 'failure']) {
    test(`ignores an obsolete ${outcome} after switching task pages`, async () => {
        let resolve;
        let reject;
        const pending = new Promise((res, rej) => { resolve = res; reject = rej; });
        const h = harness(() => pending);
        const request = h.run([7]);
        h.page(200);
        const before = h.state();
        const actionCount = h.calls.length;
        if (outcome === 'success') {
            resolve([{ taskId: 7, stage: JobStage.VALIDATION, state: JobState.NEW }]);
        } else {
            reject(new Error('obsolete request failed'));
        }
        await request;
        assert.equal(h.state(), before);
        assert.equal(h.calls.length, actionCount);
    });
}

test('renders default legend text with all 12 selected bar colors, counts, and weights', () => {
    const jobs = cases.flatMap(([stage, state], index) => (
        Array.from({ length: index + 1 }, () => ({ taskId: 7, stage, state }))
    ));
    const summary = aggregate(jobs, [7])[7];
    const html = renderToStaticMarkup(React.createElement(Progress, { summary, totalJobs: 84 }));
    const expected = cases.map(([stage, state, color], index) => [
        `${stage}-${state.replace(/ /g, '-')}`, `${stage} / ${state}`, index + 1, color,
    ]).concat([['inaccessible', 'not available', 6, '#c1c1c1']]);
    for (const [key, label, count, color] of expected) {
        const legend = html.match(new RegExp(`<span[^>]*class="[^"]*cvat-jobs-legend-${key}(?: |\")[^>]*>`));
        assert.ok(legend, `missing legend for ${label}`);
        assert.doesNotMatch(legend[0], /style=/, `expected default text color for ${label}`);
        assert.match(html, new RegExp(`cvat-jobs-legend-${key}[^>]*><strong>• ${count} ${label} `));
        const segment = html.match(new RegExp(`<div[^>]*class="[^"]*cvat-jobs-progress-${key}(?: |\")[^>]*>`));
        assert.ok(segment, `missing segment for ${label}`);
        assert.match(segment[0], new RegExp(`flex-grow:${count}(?:;|\")`));
        assert.match(segment[0], new RegExp(`background-color:${color}(?:;|\")`));
        assert.match(segment[0], new RegExp(`title="${count} ${label}"`));
    }
    assert.equal((html.match(/cvat-task-item-jobs-progress-segment/g) || []).length, 13);
    assert.match(html, /• 84 total/);
});

test('omits zero buckets and never renders a negative inaccessible segment', () => {
    const empty = aggregate([], [7])[7];
    const html = renderToStaticMarkup(React.createElement(Progress, { summary: empty, totalJobs: 0 }));
    assert.doesNotMatch(html, /cvat-jobs-legend-|cvat-task-item-jobs-progress-segment/);
    assert.match(html, /• 0 total/);
    const summary = aggregate([{ taskId: 7, stage: JobStage.ANNOTATION, state: JobState.NEW }], [7])[7];
    const extraJob = renderToStaticMarkup(React.createElement(Progress, { summary, totalJobs: 0 }));
    assert.doesNotMatch(extraJob, /inaccessible|not available/);
});

test('annotation/new text remains readable above the default gray progress bar in a browser', {
    skip: !process.env.BROWSER_BIN && 'Set BROWSER_BIN to a Chrome/Chromium executable',
}, () => {
    const { execFileSync } = require('node:child_process');
    const { mkdtempSync, rmSync, writeFileSync } = require('node:fs');
    const { tmpdir } = require('node:os');
    const { pathToFileURL } = require('node:url');
    const { createCache, extractStyle, StyleProvider } = dependency('@ant-design/cssinjs');
    const sass = dependency('sass');
    const directory = mkdtempSync(path.join(tmpdir(), 'cvat-legend-browser-'));

    try {
        const summary = aggregate([{
            taskId: 18594, stage: JobStage.ANNOTATION, state: JobState.NEW,
        }], [18594])[18594];
        const cache = createCache();
        const markup = renderToStaticMarkup(React.createElement(StyleProvider, { cache },
            React.createElement('div', { className: 'cvat-tasks-list-item' },
                React.createElement('div', { className: 'cvat-task-item-progress-wrapper' },
                    React.createElement(Progress, { summary, totalJobs: 1 })))));
        const { css } = sass.compile(path.join(cvatRoot, 'cvat-ui/src/components/tasks-page/styles.scss'), {
            loadPaths: [path.join(cvatRoot, 'cvat-ui/src')],
        });
        const fixture = path.join(directory, 'legend.html');
        writeFileSync(fixture, `<!doctype html><html><head><meta charset="utf-8">
            ${extractStyle(cache)}<style>${css}</style></head><body>${markup}
            <script>
                const legend = document.querySelector('.cvat-jobs-legend-annotation-new strong');
                const segment = document.querySelector('.cvat-jobs-progress-annotation-new');
                const card = document.querySelector('.cvat-tasks-list-item');
                const result = document.createElement('pre');
                result.id = 'browser-result';
                result.textContent = JSON.stringify({
                    text: legend.textContent.trim(),
                    textColor: getComputedStyle(legend).color,
                    background: getComputedStyle(card).backgroundColor,
                    barColor: getComputedStyle(segment).backgroundColor,
                });
                document.body.append(result);
            </script></body></html>`);
        const output = execFileSync(process.env.BROWSER_BIN, [
            '--headless', '--disable-gpu', '--disable-background-networking',
            '--no-first-run', '--no-default-browser-check',
            `--user-data-dir=${path.join(directory, 'profile')}`,
            '--dump-dom', pathToFileURL(fixture).href,
        ], { encoding: 'utf8', timeout: 30000, maxBuffer: 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
        const result = output.match(/<pre id="browser-result">([^<]+)<\/pre>/);
        assert.ok(result, 'browser did not report computed legend colors');
        const { text, textColor, background, barColor } = JSON.parse(result[1]);
        assert.equal(text, '• 1 annotation / new');
        assert.equal(background, 'rgb(255, 255, 255)');
        assert.equal(barColor, 'rgb(193, 193, 193)');

        // Composite the actual text color onto the white task card before
        // calculating contrast. This catches inherited CSS as well as inline color.
        const [red, green, blue, alpha = 1] = textColor.match(/[\d.]+/g).map(Number);
        const linear = [red, green, blue].map((channel) => {
            const value = (channel * alpha + 255 * (1 - alpha)) / 255;
            return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
        });
        const luminance = linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
        const contrast = 1.05 / (luminance + 0.05);
        assert.ok(contrast >= 4.5, `unreadable legend: ${textColor}, contrast ${contrast.toFixed(2)}:1`);
        console.log(`Browser legend: ${textColor}; bar: ${barColor}; contrast: ${contrast.toFixed(2)}:1`);
    } finally {
        rmSync(directory, { recursive: true, force: true });
    }
});
