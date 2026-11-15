// The page's states, rendered from supplied service responses.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage, render, text } = require('./helper.cjs');

const View = loadPage('team-analytics-view.tsx').default;

test('a refused caller sees that the page is not available, not an error', () => {
    const html = render(View, { organization: 'team-org', state: { kind: 'denied' } });
    assert.match(text(html), /Team analytics is not available/);
    assert.match(text(html), /This page is for administrators of this CVAT instance\./);
    assert.doesNotMatch(text(html), /owner|maintainer/);
    assert.match(text(html), /Back to tasks/);
    assert.doesNotMatch(html, /cvat-team-analytics-error/);
});

test('an unreachable service shows an error panel on the page', () => {
    const html = render(View, { organization: 'team-org', state: { kind: 'error' } });
    assert.match(html, /cvat-team-analytics-error/);
    assert.match(text(html), /Team analytics could not be loaded/);
});

test('while loading the page shows a spinner and no figures', () => {
    const html = render(View, { organization: 'team-org', state: { kind: 'loading' } });
    assert.match(html, /ant-spin/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});

test('the title names the organization, or instance scope when there is none', () => {
    const ready = { kind: 'ready', overview: { by_annotator: { rows: [] } } };
    assert.match(text(render(View, { organization: 'team-org', state: ready })),
        /Team analytics Organization team-org · annotation work inside jobs/);
    assert.match(text(render(View, { organization: null, state: ready })),
        /Team analytics All organizations and personal workspaces · annotation work inside jobs/);
});
