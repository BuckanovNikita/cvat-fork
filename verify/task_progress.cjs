// Run after installing cvat's dependencies: node --test verify/task_progress.cjs
// Executes the fork's TypeScript and React components; only API and unrelated
// application boundaries are mocked. No server or browser is required.
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
const Progress = loadSource('cvat-ui/src/components/tasks-page/task-jobs-progress.tsx').default;

const cases = [
    [JobStage.ANNOTATION, JobState.NEW, 'annotationNew'],
    [JobStage.ANNOTATION, JobState.IN_PROGRESS, 'annotating'],
    [JobStage.ANNOTATION, JobState.COMPLETED, 'annotating'],
    [JobStage.ANNOTATION, JobState.REJECTED, 'rejected'],
    [JobStage.VALIDATION, JobState.NEW, 'validation'],
    [JobStage.VALIDATION, JobState.IN_PROGRESS, 'validation'],
    [JobStage.VALIDATION, JobState.COMPLETED, 'validation'],
    [JobStage.VALIDATION, JobState.REJECTED, 'rejected'],
    [JobStage.ACCEPTANCE, JobState.NEW, 'acceptance'],
    [JobStage.ACCEPTANCE, JobState.IN_PROGRESS, 'acceptance'],
    [JobStage.ACCEPTANCE, JobState.COMPLETED, 'acceptance'],
    [JobStage.ACCEPTANCE, JobState.REJECTED, 'rejected'],
];

for (const [stage, state, bucket] of cases) {
    test(`classifies ${stage}/${state} as ${bucket}`, () => {
        const result = aggregate([{ taskId: 7, stage, state }], [7])[7];
        assert.equal(result[bucket], 1);
        assert.equal(result.fetched, 1);
        assert.equal(Object.values(result).reduce((sum, count) => sum + count, 0), 2);
    });
}

test('isolates tasks, initializes missing jobs, and ignores unrelated/null task IDs', () => {
    const job = { stage: JobStage.ANNOTATION, state: JobState.NEW };
    const result = aggregate([7, 7, 8, 999, null].map((taskId) => ({ ...job, taskId })), [7, 8, 9]);
    assert.deepEqual(Object.keys(result), ['7', '8', '9']);
    assert.equal(result[7].annotationNew, 2);
    assert.equal(result[8].annotationNew, 1);
    assert.ok(Object.values(result[9]).every((count) => count === 0));
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
    assert.equal(h.state().jobsSummary.data[7].acceptance, 1);
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
    assert.equal(h.state().jobsSummary.data[7].annotationNew, 1);
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

test('renders matching legend counts and bar weights including inaccessible jobs', () => {
    const summary = { annotationNew: 1, annotating: 2, validation: 3, acceptance: 4, rejected: 5, fetched: 15 };
    const html = renderToStaticMarkup(React.createElement(Progress, { summary, totalJobs: 21 }));
    for (const [key, label, count] of [
        ['annotation-new', 'not started', 1], ['annotating', 'annotating', 2],
        ['validation', 'on review', 3], ['acceptance', 'accepted', 4],
        ['rejected', 'rejected', 5], ['inaccessible', 'not available', 6],
    ]) {
        assert.match(html, new RegExp(`cvat-jobs-legend-${key}[^>]*><strong>• ${count} ${label} `));
        assert.match(html, new RegExp(`cvat-jobs-progress-${key}" style="flex-grow:${count}" title="${count} ${label}"`));
    }
    assert.match(html, /• 21 total/);
});

test('omits zero buckets and never renders a negative inaccessible segment', () => {
    const empty = aggregate([], [7])[7];
    const html = renderToStaticMarkup(React.createElement(Progress, { summary: empty, totalJobs: 0 }));
    assert.doesNotMatch(html, /cvat-jobs-legend-|cvat-task-item-jobs-progress-segment/);
    assert.match(html, /• 0 total/);
    const summary = { ...empty, annotationNew: 1, fetched: 1 };
    const extraJob = renderToStaticMarkup(React.createElement(Progress, { summary, totalJobs: 0 }));
    assert.doesNotMatch(extraJob, /inaccessible|not available/);
});
