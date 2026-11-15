// Definitions: the terms the overview's figures use carry their definition, worded from GLOSSARY.md, as a tooltip
// on the words themselves (hover and keyboard focus), once per card or table header; there is no block of
// definitions at the end of the overview, and full views are unchanged.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, suppliedService,
} = require('./helper.cjs');

const HOUR = 3600000;
const PERIOD = {
    name: 'week', first_day: '2026-11-07', last_day: '2026-11-13', month: null, to_date: false, unit: 'day',
};
const operation = (name, objects, share) => ({
    operation: name, objects, timed_objects: objects, time_ms: share * 10 * HOUR, average_ms: objects ? 3000 : null,
    share, hotkey_objects: 1, mouse_objects: 1,
});
const method = (name, objects) => ({
    method: name, objects, timed_objects: objects, time_ms: objects * 3000, average_ms: 3000, share: 0.3,
});
const OVERVIEW = {
    period: PERIOD,
    processed: true,
    by_annotator: { rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 9 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    by_project: { rows: [{ project_id: 0, working_time_ms: 9 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    headline: { annotators: 1, projects: 1 },
    filters: { project: null, annotator: null },
    time_series: { unit: 'day', buckets: [{ start: '2026-11-07', working_time_ms: 9 * HOUR }] },
    sessions: { sessions: 3, average_ms: 3 * HOUR, total_ms: 9 * HOUR, by_annotator: [] },
    operations: {
        legacy: false,
        shapes: 'bounding_boxes',
        working_time_ms: 10 * HOUR,
        active_time_ms: 10 * HOUR,
        rows: [operation('creation', 30, 0.3), operation('alignment', 10, 0.1), operation('class_change', 2, 0.1),
            operation('deletion', 1, 0.1), operation('other', 0, 0.4)],
    },
    creation_methods: {
        shapes: 'bounding_boxes',
        rows: [method('drawn', 20), method('pasted', 5), method('propagated', 5)],
        total: { objects: 30, timed_objects: 30, time_ms: 90000, average_ms: 3000 },
        model: { objects: 4, share: 0.12 },
        technical_accounts: 1,
    },
};
const DETAILS = {
    by: 'annotators', page: 1, page_size: 10, total: 1, legacy: false, shapes: 'bounding_boxes', processed: true,
    technical_accounts: 1,
    rows: [{
        id: 11, user_name: 'alice', projects: 1, sessions: 3, working_time_ms: 9 * HOUR, drawn: 20, pasted: 5,
        propagated: 5, model: 4, saved_boxes: 0, alignments: 10, class_changes: 2, deletions: 1,
        average_create_ms: 3000, hotkey_share: 0.5,
    }],
};
const LIST = {
    period: PERIOD, processed: true, by: 'annotators', legacy: false, shapes: 'bounding_boxes',
    total: { count: 0, working_time_ms: 0 }, rows: [],
};

const WORDING = {
    Session: 'One uninterrupted interval of job work by one person, at most a day long. A pause longer than five ' +
        'minutes ends it. Seen for a single project, a session counts if it touched that project, and its length ' +
        'is only the time spent inside it.',
    'Working time': 'The time the server counts as worked, the same figure Grafana reports. It is the only total: ' +
        'every breakdown of time adds up to it.',
    'Time per operation': "The time from a person's previous action to the end of the operation, so that finding, " +
        'deciding and pointing are part of it. A pause longer than 100 seconds before an action belongs to no ' +
        'operation.',
    Model: 'Created without a person drawing it: saved by a technical account or produced by the built-in ' +
        'detector. Model boxes have counts but no time.',
};

function answer(url) {
    if (url.includes('/details?')) return { body: DETAILS };
    if (url.includes('/list?')) return { body: LIST };
    if (url.includes('/status?')) return { body: {} };
    if (url.includes('/trends?')) return { status: 500, body: {} };
    return { body: OVERVIEW };
}

const { createMemoryHistory } = dependency('history');

async function opened(search, check) {
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const { request } = suppliedService(answer);
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': {
            useSelector: (select) => select({
                organizations: { current: { slug: 'team-org' } }, shortcuts: { keyMap: {}, normalizedKeyMap: {} },
            }),
        },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        await check(view.container, view);
    } finally {
        await view.unmount();
    }
}

const terms = (container) => [...container.querySelectorAll('.cvat-team-analytics-term')];

// the card or table a term is in, by its first cvat-team-analytics-* class
function placeOf(term) {
    const card = term.closest('section, .cvat-team-analytics-details');
    const name = [...card.classList].find((value) => value.startsWith('cvat-team-analytics-') &&
        value !== 'cvat-team-analytics-card');
    return name.replace('cvat-team-analytics-', '');
}

// the tooltip that describes a term (rendered hidden in document.body until it opens)
function tooltipOf(term) {
    const id = term.getAttribute('aria-describedby');
    assert.ok(id, 'the term names its description');
    return document.getElementById(id);
}

// antd hides a tooltip that never opened with display: none, and one that closed with its hidden class
function isShown(tooltip) {
    const popup = tooltip.closest('.ant-tooltip');
    return !popup.classList.contains('ant-tooltip-hidden') && popup.style.display !== 'none';
}

async function wait(ms) {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)); });
}

test('there is no block of definitions at the end of the overview', async () => {
    await opened('?period=week', (container) => {
        assert.ok(container.querySelector('.cvat-team-analytics-cards'), 'the overview is shown');
        assert.equal(container.querySelector('.cvat-team-analytics-definitions') === null, true);
        assert.doesNotMatch(container.textContent, /One uninterrupted interval of job work/);
    });
});

test('the terms sit on the words of the overview, once per card or table header', async () => {
    await opened('?period=week', (container) => {
        assert.deepEqual(terms(container).map((term) => [placeOf(term), term.textContent]), [
            ['sessions', 'Sessions'],
            ['average-creation', 'Avg time per box'],
            ['time-chart', 'Working time'],
            ['split', 'working time'],
            ['operations', 'Avg time'],
            ['creation-methods', 'Avg time'],
            ['creation-methods', 'Model'],
            ['working-time-by-project', 'Working time'],
            ['working-time-by-annotator', 'Working time'],
            ['details', 'Sessions'],
            ['details', 'Working time'],
            ['details', 'Model'],
            ['details', 'Avg time to create'],
        ]);
    });
});

test('each term is focusable and described by a tooltip with the glossary wording', async () => {
    await opened('?period=week', (container) => {
        const byWords = {
            Sessions: 'Session',
            'Working time': 'Working time',
            'working time': 'Working time',
            'Avg time': 'Time per operation',
            'Avg time per box': 'Time per operation',
            'Avg time to create': 'Time per operation',
            Model: 'Model',
        };
        for (const term of terms(container)) {
            assert.equal(term.tagName, 'BUTTON', `${term.textContent} is focusable`);
            assert.equal(term.getAttribute('type'), 'button');
            const tooltip = tooltipOf(term);
            assert.ok(tooltip, `${term.textContent}: its tooltip is in the document before it opens`);
            assert.equal(tooltip.getAttribute('role'), 'tooltip');
            assert.equal(tooltip.textContent, WORDING[byWords[term.textContent]], term.textContent);
            assert.equal(isShown(tooltip), false, 'hidden until asked for');
            assert.equal(container.contains(tooltip), false, 'outside the cards, so no table clips it');
        }
    });
});

test('a term shows one tooltip only: neither it nor anything around it in its card has a native title', async () => {
    await opened('?period=week', (container) => {
        const all = terms(container);
        assert.equal(all.length, 13);
        for (const term of all) {
            const card = term.closest('section, .cvat-team-analytics-details');
            const titled = [];
            for (let element = term; element && element !== card.parentElement; element = element.parentElement) {
                if (element.hasAttribute('title')) titled.push(`${element.tagName.toLowerCase()} "${element.getAttribute('title')}"`);
            }
            assert.deepEqual(titled, [], `${placeOf(term)} · ${term.textContent}`);
        }
    });
});

test('hovering a term shows its definition, leaving hides it', async () => {
    await opened('?period=week', async (container) => {
        const term = container.querySelector('.cvat-team-analytics-sessions .cvat-team-analytics-term');
        await act(async () => { term.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true })); });
        await wait(200);
        assert.equal(isShown(tooltipOf(term)), true);
        assert.equal(tooltipOf(term).textContent, WORDING.Session);
        await act(async () => {
            term.dispatchEvent(new window.MouseEvent('mouseout', { bubbles: true, relatedTarget: document.body }));
        });
        await wait(300);
        assert.equal(isShown(tooltipOf(term)), false);
    });
});

test('a tap or click on a term shows its definition', async () => {
    await opened('?period=week', async (container) => {
        const term = container.querySelector('.cvat-team-analytics-details .cvat-team-analytics-term');
        await act(async () => { term.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
        await wait(50);
        assert.equal(isShown(tooltipOf(term)), true);
        assert.equal(tooltipOf(term).textContent, WORDING.Session);
    });
});

test('focusing a term shows its definition; Escape hides it', async () => {
    await opened('?period=week', async (container) => {
        const term = container.querySelector('.cvat-team-analytics-creation-methods .cvat-team-analytics-model-row ' +
            '.cvat-team-analytics-term');
        await act(async () => { term.focus(); });
        await wait(50);
        assert.equal(document.activeElement === term, true);
        assert.equal(isShown(tooltipOf(term)), true);
        assert.equal(tooltipOf(term).textContent, WORDING.Model);
        await act(async () => {
            term.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        });
        await wait(300);
        assert.equal(isShown(tooltipOf(term)), false);
        assert.equal(document.activeElement === term, true, 'focus stays on the term');
    });
});

test('a tooltip opened by hover is dismissed by Escape, which is left to other handlers too', async () => {
    // the keydown listeners put on the document while the page is open, and those taken off again
    const added = new Set();
    const { addEventListener, removeEventListener } = document;
    document.addEventListener = function counted(type, listener, ...rest) {
        if (type === 'keydown') added.add(listener);
        return addEventListener.call(this, type, listener, ...rest);
    };
    document.removeEventListener = function counted(type, listener, ...rest) {
        if (type === 'keydown') added.delete(listener);
        return removeEventListener.call(this, type, listener, ...rest);
    };
    try {
        await hoverThenEscape();
    } finally {
        document.addEventListener = addEventListener;
        document.removeEventListener = removeEventListener;
    }
    assert.equal(added.size, 0, 'no keydown listener of the page is left on the document');
});

async function hoverThenEscape() {
    await opened('?period=week', async (container) => {
        const term = container.querySelector('.cvat-team-analytics-sessions .cvat-team-analytics-term');
        await act(async () => { term.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true })); });
        await wait(200);
        assert.equal(isShown(tooltipOf(term)), true);
        assert.notEqual(document.activeElement === term, true, 'the focus is elsewhere');
        // another handler of the same key, as an open selector or modal would have
        let seen = 0;
        const other = (event) => { if (event.key === 'Escape') seen += 1; };
        window.addEventListener('keydown', other);
        const escape = new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
        try {
            await act(async () => { document.body.dispatchEvent(escape); });
        } finally {
            window.removeEventListener('keydown', other);
        }
        await wait(300);
        assert.equal(isShown(tooltipOf(term)), false, 'dismissed');
        assert.equal(seen, 1, 'the press reaches the other handler');
        assert.equal(escape.defaultPrevented, false);
        // opened again and left open: the page goes away with it open
        await act(async () => { term.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true })); });
        await wait(200);
        assert.equal(isShown(tooltipOf(term)), true);
    });
}

test('with the focus in an open selector, one Escape closes the selector and a hover-opened definition', async () => {
    await opened('?period=week', async (container) => {
        const annotator = container.querySelector('.cvat-team-analytics-filter-annotator');
        await act(async () => {
            annotator.querySelector('.cvat-team-analytics-filter-button')
                .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
        });
        await wait(50);
        const search = annotator.querySelector('input[role="combobox"]');
        assert.equal(document.activeElement === search, true, 'the focus is in the selector');
        const term = container.querySelector('.cvat-team-analytics-sessions .cvat-team-analytics-term');
        await act(async () => { term.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true })); });
        await wait(200);
        assert.equal(isShown(tooltipOf(term)), true);
        // the selector stops the key from bubbling
        await act(async () => {
            search.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
        });
        await wait(300);
        assert.equal(annotator.querySelector('[role="listbox"]') === null, true, 'the selector closes');
        assert.equal(isShown(tooltipOf(term)), false, 'and the definition is dismissed');
    });
});

test('a full view shows no definitions, for a chart and for a trend', async () => {
    for (const search of ['?period=week&view=time', '?period=week&view=annotators', '?period=week&view=trend-working_time']) {
        // eslint-disable-next-line no-await-in-loop
        await opened(search, (container) => {
            assert.ok(container.querySelector('.cvat-team-analytics-full'), `${search} opens a full view`);
            assert.deepEqual(terms(container), [], `${search} shows no definitions`);
        });
    }
});
