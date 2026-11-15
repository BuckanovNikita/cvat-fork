// The route: the page loads on demand and a failure stays on the page (rendered in jsdom).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, loadPage, mount, suppliedService,
} = require('./helper.cjs');

const ORGANIZATION_STATE = { organizations: { current: { slug: 'team-org' } } };
const reduxBoundary = { useSelector: (select) => select(ORGANIZATION_STATE) };
const routerBoundary = { useHistory: () => ({ push() {} }) };

function pageModule(request) {
    return loadPage('team-analytics-page.tsx', {
        'react-redux': reduxBoundary,
        'react-router': routerBoundary,
        './service': { ...loadPage('service.ts'), requestService: request },
    });
}

function route(pageBoundary) {
    return loadPage('team-analytics-route.tsx', pageBoundary).default;
}

// Something else CVAT renders next to the page, e.g. the header.
const Sibling = () => React.createElement('nav', { id: 'rest-of-cvat' }, 'Projects Tasks Jobs');
const app = (Route) => React.createElement('div', null, React.createElement(Sibling), React.createElement(Route));

test('the page module is loaded only when the route renders, then shows the figures', async () => {
    const { request, requests } = suppliedService(() => ({
        body: { by_annotator: { rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 7200000 }] } },
    }));
    let loads = 0;
    const boundaries = {};
    Object.defineProperty(boundaries, './team-analytics-page', {
        enumerable: true,
        get() { loads += 1; return pageModule(request); },
    });
    const Route = route(boundaries);
    assert.equal(loads, 0, 'the page must not be loaded with the application');

    const view = await mount(app(Route));
    await view.settle();
    assert.equal(loads, 1);
    assert.equal(requests.filter((request) => request.url.includes('/overview')).length, 1);
    assert.match(view.container.textContent, /alice/);
    assert.match(view.container.textContent, /2\.0 h/);
    await view.unmount();
});

test('a page that fails to load shows an error panel on that page and the rest of CVAT keeps working', async () => {
    const boundaries = {};
    Object.defineProperty(boundaries, './team-analytics-page', {
        enumerable: true,
        get() { throw new Error('Loading chunk team-analytics failed.'); },
    });
    const originalError = console.error;
    console.error = () => {}; // React reports the caught error; it is expected here
    try {
        const view = await mount(app(route(boundaries)));
        await view.settle();
        assert.ok(view.container.querySelector('.cvat-team-analytics-error'));
        assert.match(view.container.textContent, /Team analytics could not be loaded/);
        assert.ok(view.container.querySelector('#rest-of-cvat'), 'the rest of CVAT must still render');
        await view.unmount();
    } finally {
        console.error = originalError;
    }
});

test('a page that throws while rendering is contained the same way', async () => {
    const boundaries = { './team-analytics-page': { default: () => { throw new Error('render failed'); } } };
    const originalError = console.error;
    console.error = () => {};
    try {
        const view = await mount(app(route(boundaries)));
        await view.settle();
        assert.ok(view.container.querySelector('.cvat-team-analytics-error'));
        assert.ok(view.container.querySelector('#rest-of-cvat'));
        await view.unmount();
    } finally {
        console.error = originalError;
    }
});

test('an unreachable service shows the error panel on the page', async () => {
    const { request } = suppliedService(() => new TypeError('Failed to fetch'));
    const Route = route({ './team-analytics-page': pageModule(request) });
    const view = await mount(app(Route));
    await view.settle();
    assert.ok(view.container.querySelector('.cvat-team-analytics-error'));
    assert.ok(view.container.querySelector('#rest-of-cvat'));
    await view.unmount();
});

test('the page leaves the organization selected in CVAT to cvat-core and names none itself', async () => {
    const { request, requests } = suppliedService(() => ({ body: { by_annotator: { rows: [] } } }));
    const view = await mount(app(route({ './team-analytics-page': pageModule(request) })));
    await view.settle();
    assert.ok(requests.length > 0);
    for (const sent of requests) assert.equal(Object.hasOwn(sent.params, 'org'), false, sent.url);
    await view.unmount();
});
