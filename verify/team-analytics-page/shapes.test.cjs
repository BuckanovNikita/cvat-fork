// Bounding boxes and All shapes: the switch, what the operation figures say they cover, and the switch
// kept in the page address and sent to the service.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, render, suppliedService, text,
} = require('./helper.cjs');

const { createMemoryHistory } = dependency('history');

const View = loadPage('team-analytics-view.tsx').default;
const service = loadPage('service.ts');
const address = loadPage('address.ts');
const HOUR = 3600000;

function row(operation, objects, timeMs, averageMs, share) {
    return { operation, objects, timed_objects: objects, time_ms: timeMs, average_ms: averageMs, share };
}

function operations(shapes, { legacy = false, created = 120 } = {}) {
    return {
        legacy,
        shapes,
        working_time_ms: 10 * HOUR,
        active_time_ms: 10 * HOUR,
        rows: [
            row('creation', created, 2 * HOUR, 3000, 0.2),
            row('alignment', 40, 0.5 * HOUR, 2000, 0.05),
            row('class_change', 3, 0.1 * HOUR, 1000, 0.01),
            row('deletion', 10, 0.2 * HOUR, 9000, 0.02),
            row('other', 0, 7.2 * HOUR, null, 0.72),
        ],
    };
}

const WEEK = {
    period: 'week', month: null, project: null, annotator: null, shapes: 'bounding_boxes',
};

function ready(figures, shown = WEEK) {
    return {
        organization: 'team-org',
        state: { kind: 'ready', overview: { by_annotator: { rows: [] }, operations: figures } },
        address: shown,
        onAddressChange() {},
    };
}

function section(html, className) {
    const match = html.match(new RegExp(`<section[^>]*${className}[^>]*>(.*?)</section>`));
    assert.ok(match, `${className} is shown`);
    // the card's Full view button (full-view.test.cjs) is not part of its wording
    return text(match[1].replace(/<button[^>]*cvat-team-analytics-full-view-button.*?<\/button>/g, ''));
}

function switchButtons(html) {
    const group = html.match(/<div[^>]*aria-label="Shapes"[^>]*>(.*?)<\/div>/);
    if (!group) return null;
    return [...group[1].matchAll(/<button[^>]*aria-pressed="(true|false)"[^>]*>(.*?)<\/button>/g)]
        .map((button) => `${text(button[2])}${button[1] === 'true' ? ' (on)' : ''}`);
}

test('bounding box figures name boxes in every operation card', () => {
    const html = render(View, ready(operations('bounding_boxes')));
    assert.equal(section(html, 'cvat-team-analytics-objects-created'), 'Boxes created 120 by annotators');
    assert.equal(section(html, 'cvat-team-analytics-average-creation'), 'Avg time per box 3.0 s to create one');
    assert.ok(section(html, 'cvat-team-analytics-split').startsWith('Where working time goes Bounding boxes · 10.0 h'));
    assert.ok(section(html, 'cvat-team-analytics-operations')
        .startsWith('Bounding box operations Counts and average time per box · bounding boxes'));
});

test('all-shape figures name objects in every operation card', () => {
    const html = render(View, ready(operations('all'), { ...WEEK, shapes: 'all' }));
    assert.equal(section(html, 'cvat-team-analytics-objects-created'), 'Objects created 120 by annotators');
    assert.equal(section(html, 'cvat-team-analytics-average-creation'), 'Avg time per object 3.0 s to create one');
    assert.ok(section(html, 'cvat-team-analytics-split').startsWith('Where working time goes All shapes · 10.0 h'));
    assert.ok(section(html, 'cvat-team-analytics-operations')
        .startsWith('Object operations Counts and average time per object · all shapes'));
});

test('the filter row has a switch between Bounding boxes and All shapes', () => {
    assert.deepEqual(switchButtons(render(View, ready(operations('bounding_boxes')))),
        ['Bounding boxes (on)', 'All shapes']);
    assert.deepEqual(switchButtons(render(View, ready(operations('all'), { ...WEEK, shapes: 'all' }))),
        ['Bounding boxes', 'All shapes (on)']);
});

test('a legacy period shows all shapes with the notice and no switch', () => {
    const html = render(View, ready(operations('all', { legacy: true })));
    assert.equal(switchButtons(html), null);
    assert.match(html, /cvat-team-analytics-legacy-notice/);
    assert.equal(section(html, 'cvat-team-analytics-objects-created'), 'Objects created 120 by annotators');
});

test('the page opens on Bounding boxes; All shapes is kept in the address', () => {
    const now = new Date(2026, 10, 13);
    assert.equal(address.readAddress('', now).shapes, 'bounding_boxes');
    assert.equal(address.readAddress('?shapes=all', now).shapes, 'all');
    assert.equal(address.readAddress('?shapes=circles', now).shapes, 'bounding_boxes');
    assert.equal(address.addressSearch({ ...WEEK, shapes: 'all' }, ''), '?shapes=all&period=week');
    assert.equal(address.addressSearch(WEEK, '?shapes=all'), '?period=week');
});

test('the switch is sent to the service with the other selections', async () => {
    const { request, requests } = suppliedService(() => ({ body: { by_annotator: { rows: [] } } }));
    await service.loadOverview({ organization: 'team-org', timeZone: 'UTC', shapes: 'bounding_boxes' }, request);
    await service.loadOverview({ organization: 'team-org', timeZone: 'UTC', shapes: 'all' }, request);
    const sent = requests.map((request) => new URL(request.url, 'http://localhost').searchParams.get('shapes'));
    assert.deepEqual(sent, ['bounding_boxes', 'all']);
});

// --- the mounted page: the switch applies to every operation figure ---------------------------------

function answer(url) {
    if (url.includes('/status')) return { body: {} };
    const shapes = new URL(url, 'http://localhost').searchParams.get('shapes');
    return {
        body: {
            by_annotator: { rows: [], rest: { count: 0, working_time_ms: 0 } },
            operations: operations(shapes, { created: shapes === 'all' ? 300 : 120 }),
        },
    };
}

test('switching to All shapes reads and shows all-shape figures and records the choice', async () => {
    const history = createMemoryHistory({ initialEntries: ['/team-analytics'] });
    const { request, requests } = suppliedService(answer);
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    const created = (container) => text(container.querySelector('.cvat-team-analytics-objects-created').innerHTML);
    const lastShapes = () => {
        const url = requests.filter((request) => !request.url.includes('/status')).at(-1).url;
        return new URL(url, 'http://localhost').searchParams.get('shapes');
    };

    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        assert.equal(lastShapes(), 'bounding_boxes');
        assert.equal(created(view.container), 'Boxes created 120 by annotators');

        const all = [...view.container.querySelectorAll('[aria-label="Shapes"] button')]
            .find((button) => button.textContent === 'All shapes');
        await act(async () => { all.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
        await view.settle();

        assert.equal(lastShapes(), 'all');
        assert.equal(history.location.search, '?shapes=all&period=week');
        assert.equal(created(view.container), 'Objects created 300 by annotators');
        assert.match(text(view.container.querySelector('.cvat-team-analytics-operations').innerHTML),
            /^Object operations /);
    } finally {
        await view.unmount();
    }
});
