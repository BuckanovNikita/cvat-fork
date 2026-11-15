// Sessions: the headline figure (number of sessions and their average length) and the per-annotator
// figures the service sends.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, render, suppliedService, text } = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;
const service = loadPage('service.ts');
const MINUTE = 60000;

const SESSIONS = {
    sessions: 42,
    average_ms: 38 * MINUTE,
    total_ms: 42 * 38 * MINUTE,
    by_annotator: [
        { user_id: 11, user_name: 'alice', sessions: 30, average_ms: 40 * MINUTE, total_ms: 1200 * MINUTE },
        { user_id: 12, user_name: 'bob', sessions: 12, average_ms: 33 * MINUTE, total_ms: 396 * MINUTE },
    ],
};

function ready(sessions) {
    return { organization: 'team-org', state: { kind: 'ready', overview: { by_annotator: { rows: [] }, sessions } } };
}

function headline(html) {
    const match = html.match(/<section[^>]*cvat-team-analytics-sessions[^>]*>(.*?)<\/section>/);
    assert.ok(match, 'the sessions headline is shown');
    return text(match[1]);
}

test('the headline shows the number of sessions and their average length', () => {
    assert.equal(headline(render(View, ready(SESSIONS))), 'Sessions 42 average 38 min');
});

test('the average length reads in seconds, minutes or hours as it grows', () => {
    const average = (ms) => headline(render(View, ready({ ...SESSIONS, average_ms: ms }))).replace(/^Sessions 42 average /, '');
    assert.equal(average(0), '0 s');
    assert.equal(average(45000), '45 s');
    assert.equal(average(59.6 * MINUTE), '60 min');
    assert.equal(average(60 * MINUTE), '1.0 h');
    assert.equal(average(150 * MINUTE), '2.5 h');
});

test('large session counts keep digit grouping', () => {
    assert.match(headline(render(View, ready({ ...SESSIONS, sessions: 12345 }))), /Sessions 12,345 /);
});

test('a period without sessions says no sessions instead of an average', () => {
    assert.equal(headline(render(View, ready({ sessions: 0, average_ms: 0, total_ms: 0, by_annotator: [] }))),
        'Sessions 0 no sessions in this period');
});

test('per-annotator session counts and average lengths reach the page', async () => {
    const { request } = suppliedService(() => ({ body: { by_annotator: { rows: [] }, sessions: SESSIONS } }));
    const state = await service.loadOverview({ organization: 'team-org', timeZone: 'UTC' }, request);
    assert.equal(state.kind, 'ready');
    assert.deepEqual(state.overview.sessions.by_annotator.map((row) => [row.user_name, row.sessions, row.average_ms]),
        [['alice', 30, 40 * MINUTE], ['bob', 12, 33 * MINUTE]]);
});
