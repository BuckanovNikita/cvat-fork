// Each refusal of the analytics service, as the page shows it (mounted in jsdom, supplied answers).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, domAvailable, loadPage, mount, suppliedFetch,
} = require('./helper.cjs');

const domTest = (name, fn) => test(name, { skip: !domAvailable && 'jsdom is not installed in cvat/node_modules' }, fn);

async function visit(organization, answer) {
    const { fetch, requests } = suppliedFetch(() => answer);
    const state = { organizations: { current: organization ? { slug: organization } : null } };
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select(state) },
        'react-router': { useHistory: () => ({ push() {} }) },
        './service': { ...loadPage('service.ts'), fetchService: fetch },
    }).default;
    const view = await mount(React.createElement(Page));
    await view.settle();
    const text = view.container.textContent.replace(/\s+/g, ' ');
    const html = view.container.innerHTML;
    await view.unmount();
    return { text, html, requests };
}

const ROLES = /This page is for administrators and for owners and maintainers of the current organization\./;

domTest('an ordinary annotator without an organization sees that the page is not available and for whom', async () => {
    const { text, requests } = await visit(null, { status: 403, body: { error: 'forbidden' } });
    assert.equal(new URL(requests[0].url, 'http://localhost').searchParams.get('org'), '');
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(text, /Select an organization/);
    assert.doesNotMatch(text, /All organizations and personal workspaces/);
});

domTest('a worker or supervisor of the selected organization sees that the page is not available', async () => {
    const { text, html } = await visit('team-org', { status: 403, body: { error: 'forbidden' } });
    assert.match(text, /Team analytics is not available/);
    assert.match(text, ROLES);
    assert.doesNotMatch(html, /cvat-team-analytics-error/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});

domTest('an owner or maintainer without an organization is asked to select one, with no scope claimed', async () => {
    const { text, html } = await visit(null, { status: 403, body: { error: 'organization_required' } });
    assert.ok(html.includes('cvat-team-analytics-select-organization'));
    assert.match(text, /Select an organization/);
    assert.match(text, /No organization selected/);
    assert.doesNotMatch(text, /All organizations and personal workspaces/);
    assert.doesNotMatch(text, /not available/);
});

domTest('an ended session asks to sign in again instead of naming the roles', async () => {
    const { text, html } = await visit('team-org', { status: 401, body: { error: 'not_authenticated' } });
    assert.ok(html.includes('cvat-team-analytics-signed-out'));
    assert.match(text, /Sign in again/);
    assert.doesNotMatch(text, ROLES);
});

domTest('when CVAT cannot be reached behind the service the page shows the error panel, no figures', async () => {
    const { text, html } = await visit('team-org', { status: 503, body: { error: 'cvat_unavailable' } });
    assert.ok(html.includes('cvat-team-analytics-error'));
    assert.match(text, /Team analytics could not be loaded/);
    assert.doesNotMatch(html, /cvat-team-analytics-annotator-row/);
});
