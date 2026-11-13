// How the page reads the service: the request it sends and the state each answer becomes.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, suppliedFetch } = require('./helper.cjs');

const service = loadPage('service.ts');
const ROWS = [{ user_id: 12, user_name: 'bob', working_time_ms: 3600000 }];

test('asks the service for the week of the named organization, in the viewer time zone, with the session', async () => {
    const { fetch, requests } = suppliedFetch(() => ({ body: { by_annotator: { rows: ROWS } } }));
    await service.loadOverview({ organization: 'team-org', timeZone: 'Europe/Berlin' }, fetch);
    assert.equal(requests.length, 1);
    const url = new URL(requests[0].url, 'http://localhost');
    assert.equal(url.pathname, '/team-analytics-api/v1/overview');
    assert.equal(url.searchParams.get('org'), 'team-org');
    assert.equal(url.searchParams.get('period'), 'week');
    assert.equal(url.searchParams.get('tz'), 'Europe/Berlin');
    assert.equal(requests[0].init.credentials, 'same-origin');
});

test('without an organization it names none, so an administrator gets instance scope', async () => {
    const { fetch, requests } = suppliedFetch(() => ({ body: { by_annotator: { rows: [] } } }));
    await service.loadOverview({ organization: null, timeZone: 'UTC' }, fetch);
    assert.equal(new URL(requests[0].url, 'http://localhost').searchParams.get('org'), '');
});

test('neither the page nor the service address starts with the Grafana prefix', () => {
    assert.equal(service.TEAM_ANALYTICS_PATH, '/team-analytics');
    assert.ok(!service.TEAM_ANALYTICS_PATH.startsWith('/analytics'));
    assert.ok(!service.SERVICE_PREFIX.startsWith('/analytics'));
    assert.ok(!service.SERVICE_PREFIX.startsWith('/api/'));
});

const answers = [
    ['figures', { status: 200, body: { by_annotator: { rows: ROWS } } }, { kind: 'ready', overview: { by_annotator: { rows: ROWS } } }],
    ['a refusal', { status: 403, body: { error: 'forbidden' } }, { kind: 'denied' }],
    ['an unauthenticated answer', { status: 401, body: { error: 'not_authenticated' } }, { kind: 'denied' }],
    ['a request to select an organization', { status: 403, body: { error: 'organization_required' } }, { kind: 'select-organization' }],
    ['CVAT unavailable behind the service', { status: 503, body: { error: 'cvat_unavailable' } }, { kind: 'error' }],
    ['a server error', { status: 502, body: 'not json' }, { kind: 'error' }],
    ['no answer at all', new TypeError('Failed to fetch'), { kind: 'error' }],
];

for (const [name, response, expected] of answers) {
    test(`turns ${name} into the ${expected.kind} state`, async () => {
        const { fetch } = suppliedFetch(() => response);
        const state = await service.loadOverview({ organization: 'team-org', timeZone: 'UTC' }, fetch);
        assert.equal(state.kind, expected.kind);
        if (expected.overview) assert.deepEqual(state.overview, expected.overview);
    });
}
