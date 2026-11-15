// How the page reads CVAT's analytics API: the request it sends and the state each answer becomes.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadCoreExceptions, loadPage, suppliedService } = require('./helper.cjs');

const service = loadPage('service.ts');
const ROWS = [{ user_id: 12, user_name: 'bob', working_time_ms: 3600000 }];

test('asks CVAT\'s API for the week, in the viewer time zone, and leaves the organization to cvat-core', async () => {
    const { request, requests } = suppliedService(() => ({ body: { by_annotator: { rows: ROWS } } }));
    await service.loadOverview({ organization: 'team-org', timeZone: 'Europe/Berlin' }, request);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].endpoint, 'overview');
    assert.deepEqual(requests[0].params, { period: 'week', tz: 'Europe/Berlin' });
});

test('without an organization it names none either, so an administrator gets instance scope', async () => {
    const { request, requests } = suppliedService(() => ({ body: { by_annotator: { rows: [] } } }));
    await service.loadOverview({ organization: null, timeZone: 'UTC' }, request);
    assert.equal(Object.hasOwn(requests[0].params, 'org'), false);
});

test('no loader sends an organization of its own', async () => {
    const { request, requests } = suppliedService(() => ({ status: 503, body: null }));
    const query = { organization: 'team-org', timeZone: 'UTC', project: 3, annotator: 11, shapes: 'all' };
    await service.loadStatus(query, request);
    await service.loadOverview(query, request);
    await service.loadList({ ...query, by: 'annotators' }, request);
    await service.loadDetails({ ...query, by: 'projects', page: 1, ids: [3] }, request);
    await service.loadTrends({
        ...query, step: 'week', compare: 'annotators', ids: [11],
    }, request);
    assert.deepEqual(requests.map((sent) => sent.endpoint), ['status', 'overview', 'list', 'details', 'trends']);
    for (const sent of requests) assert.equal(Object.hasOwn(sent.params, 'org'), false, sent.url);
});

test('the page address is unchanged and the API path is CVAT\'s, not the Grafana prefix', () => {
    assert.equal(service.TEAM_ANALYTICS_PATH, '/team-analytics');
    assert.ok(!service.TEAM_ANALYTICS_PATH.startsWith('/analytics'));
    assert.equal(service.SERVICE_PATH, 'team-analytics');
});

const answers = [
    ['figures', { status: 200, body: { by_annotator: { rows: ROWS } } }, { kind: 'ready', overview: { by_annotator: { rows: ROWS } } }],
    ['a refusal', { status: 403, body: { error: 'forbidden' } }, { kind: 'denied' }],
    ['a refusal without a body', { status: 403, body: null }, { kind: 'denied' }],
    ['an unauthenticated answer', { status: 401, body: { error: 'not_authenticated' } }, { kind: 'signed-out' }],
    ['a 403 naming organization_required (no longer sent)', { status: 403, body: { error: 'organization_required' } }, { kind: 'denied' }],
    ['analytics switched off or an unknown organization', { status: 404, body: null }, { kind: 'denied' }],
    ['an answer not ready after cvat-core\'s retries', { status: 429, body: null }, { kind: 'error' }],
    ['a bad parameter', { status: 400, body: null }, { kind: 'error' }],
    ['a failed read', { status: 503, body: { error: 'cvat_unavailable' } }, { kind: 'error' }],
    ['a server error', { status: 500, body: 'not json' }, { kind: 'error' }],
    ['no answer at all', new TypeError('Network Error'), { kind: 'error' }],
];

for (const [name, response, expected] of answers) {
    test(`turns ${name} into the ${expected.kind} state`, async () => {
        const { request } = suppliedService(() => response);
        const state = await service.loadOverview({ organization: 'team-org', timeZone: 'UTC' }, request);
        assert.equal(state.kind, expected.kind);
        if (expected.overview) assert.deepEqual(state.overview, expected.overview);
    });
}

test('a 404 or 429 of the other endpoints: 404 is a refusal of the page, 429 only a failure of that request', async () => {
    const query = { organization: 'team-org', timeZone: 'UTC' };
    const loads = [
        (request) => service.loadStatus(query, request),
        (request) => service.loadList({ ...query, by: 'projects' }, request),
        (request) => service.loadDetails({ ...query, by: 'annotators', page: 1 }, request),
        (request) => service.loadTrends({
            ...query, project: null, annotator: null, shapes: 'all', step: 'week', compare: 'projects', ids: [],
        }, request),
    ];
    for (const [status, refusals] of [[404, [{ kind: 'denied' }]], [429, []]]) {
        for (const load of loads) {
            const { request, requests } = suppliedService(() => ({ status, body: null }));
            const seen = [];
            const stop = service.onRefusal((state) => seen.push(state));
            try {
                assert.equal(await load(request), null, `${status} answers null`);
            } finally {
                stop();
            }
            assert.deepEqual(seen, refusals, `${requests[0].endpoint} on ${status}`);
        }
    }
});

// --- the real boundary: cvat-core's request function, stubbed, and the errors it throws ----------------------

const { ServerError } = loadCoreExceptions();

// cvat-core's request (server-proxy.ts `serverRequest`): the Axios response, or a ServerError for a non-2xx
// answer. An error body it does not know becomes "**<field>**: <value>" lines of the message (`generateError`).
function coreAnswering(answer) {
    const calls = [];
    const core = {
        config: { backendAPI: '/api' },
        server: {
            async request(url, data) {
                calls.push({ url, data });
                const outcome = answer(url, data);
                if (outcome instanceof Error) throw outcome;
                return outcome;
            },
        },
    };
    const real = loadPage('service.ts', { 'cvat-core-wrapper': { getCore: () => core, ServerError } });
    return { real, calls };
}

test('the real boundary asks cvat-core for /api/team-analytics/<endpoint> with GET and the params only', async () => {
    const { real, calls } = coreAnswering(() => ({ status: 200, data: { by_annotator: { rows: ROWS } } }));
    const answer = await real.requestService('overview', { period: 'week', tz: 'UTC' });
    assert.deepEqual(answer, { status: 200, body: { by_annotator: { rows: ROWS } } });
    assert.deepEqual(calls, [{ url: '/api/team-analytics/overview', data: { method: 'GET', params: { period: 'week', tz: 'UTC' } } }]);
});

const thrown = [
    ['401', new ServerError('Authentication credentials were not provided.', 401, 'Unauthorized'), { status: 401, body: null }, 'signed-out'],
    ['plain 403', new ServerError('You do not have permission to perform this action.', 403, 'Forbidden'), { status: 403, body: null }, 'denied'],
    ['403 naming organization_required', new ServerError('**error**: organization_required', 403, 'Forbidden'), { status: 403, body: null }, 'denied'],
    ['404', new ServerError('Not found.', 404, 'Not Found'), { status: 404, body: null }, 'denied'],
    ['429', new ServerError('Request was throttled.', 429, 'Too Many Requests'), { status: 429, body: null }, 'error'],
    ['503', new ServerError('**error**: read_failed', 503, 'Service Unavailable'), { status: 503, body: null }, 'error'],
];

for (const [name, error, expected, kind] of thrown) {
    test(`the real boundary turns cvat-core's ${name} error into status ${expected.status}, the ${kind} state`, async () => {
        const { real } = coreAnswering(() => error);
        assert.deepEqual(await real.requestService('overview', {}), expected);
        assert.equal((await real.loadOverview({ organization: 'team-org', timeZone: 'UTC' })).kind, kind);
    });
}

test('the real boundary passes on no answer at all, which the loaders read as a failure', async () => {
    const unreachable = new ServerError('The CVAT server is unavailable', 0, 'ERR_NETWORK');
    const { real } = coreAnswering(() => unreachable);
    await assert.rejects(real.requestService('status', {}), (error) => error === unreachable);
    assert.equal((await real.loadOverview({ organization: null, timeZone: 'UTC' })).kind, 'error');
    assert.equal(await real.loadStatus({ organization: null, timeZone: 'UTC' }), null);
});
