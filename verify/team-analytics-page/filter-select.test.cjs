// The Project and Annotator selectors of the filter row: searchable single-select dropdowns whose options are the
// projects or annotators with job work in the period, loaded when one opens (mounted page, supplied answers).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadPage, mount, suppliedService,
} = require('./helper.cjs');

const { createMemoryHistory } = dependency('history');
const HOUR = 3600000;

const OVERVIEW = {
    by_annotator: {
        rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 4 * HOUR }],
        rest: { count: 0, working_time_ms: 0 },
    },
    by_project: { rows: [{ project_id: 1, working_time_ms: 3 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    filters: { project: null, annotator: null },
};

const operations = { creation: {}, alignment: {}, class_change: {}, deletion: {}, other: { time_ms: 0 } };
const listRow = (id, userName = null) => ({
    id, user_name: userName, working_time_ms: HOUR, share: 0.5, operations, methods: {}, model: 0,
});
const PROJECTS = { by: 'projects', legacy: false, shapes: 'all', total: { count: 3, working_time_ms: 3 * HOUR },
    rows: [listRow(2), listRow(0), listRow(1)] };
const ANNOTATORS = { by: 'annotators', legacy: false, shapes: 'all', total: { count: 3, working_time_ms: 3 * HOUR },
    rows: [listRow(12, 'bob'), listRow(11, 'alice'), listRow(40, 'zoe')] };
const NAMES = { 1: 'Street scenes', 2: 'Retail shelves' };

function endpointOf(url) {
    return new URL(url, 'http://localhost').pathname.replace('/api/team-analytics/', '');
}

// `lists(by, params)` answers GET list; the overview, status and names answer as on a working server
function openPage({ search = '', lists = (by) => ({ body: by === 'projects' ? PROJECTS : ANNOTATORS }) } = {}) {
    const history = createMemoryHistory({ initialEntries: [`/team-analytics${search}`] });
    const { request, requests } = suppliedService((url, sent) => {
        const endpoint = endpointOf(url);
        if (endpoint === 'list') return lists(sent.params.by, sent.params);
        if (endpoint === 'project-names') {
            const ids = sent.params.ids.split(',');
            return { body: { names: Object.fromEntries(ids.filter((id) => NAMES[id]).map((id) => [id, NAMES[id]])) } };
        }
        if (endpoint === 'overview') return { body: OVERVIEW };
        return { body: {} };
    });
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: { slug: 'team-org' } } }) },
        'react-router': { useHistory: () => history },
        './service': { ...loadPage('service.ts'), requestService: request },
    }).default;
    return { history, requests, Page };
}

async function opened(Page, check) {
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        await check(view);
    } finally {
        await view.unmount();
    }
}

async function click(element) {
    await act(async () => { element.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
}

async function press(element, key) {
    await act(async () => {
        element.dispatchEvent(new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
    });
}

async function type(input, value) {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await act(async () => {
        setter.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
}

const selector = (container, kind) => container.querySelector(`.cvat-team-analytics-filter-${kind}`);
const button = (container, kind) => selector(container, kind).querySelector('.cvat-team-analytics-filter-button');
const options = (container, kind) => [...selector(container, kind).querySelectorAll('[role="option"]')]
    .map((option) => option.textContent);
const statusLine = (container, kind) => selector(container, kind).querySelector('.cvat-team-analytics-filter-status')
    .textContent;
const lists = (requests) => requests.filter((sent) => sent.endpoint === 'list');

test('opening a selector asks one list of its kind for the period, without the filters or the shapes', async () => {
    const { requests, Page } = openPage({ search: '?period=month&month=2026-10&annotator=11&org=team-org&shapes=all' });
    await opened(Page, async (view) => {
        assert.equal(lists(requests).length, 0, 'nothing is asked before a selector opens');
        await click(button(view.container, 'project'));
        await view.settle();
        assert.deepEqual(lists(requests).map((sent) => sent.params), [
            { period: 'month', tz: lists(requests)[0].params.tz, month: '2026-10', by: 'projects' },
        ]);
        assert.equal(button(view.container, 'project').getAttribute('aria-expanded'), 'true');
        // All first, then every project with work, No project included, named through the fork's API
        assert.deepEqual(options(view.container, 'project'),
            ['All projects', 'Retail shelves', 'No project', 'Street scenes']);
        assert.ok(requests.some((sent) => sent.endpoint === 'project-names' && sent.params.ids === '2'),
            'the unnamed listed project is named');

        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.equal(lists(requests).at(-1).params.by, 'annotators');
        assert.equal(Object.hasOwn(lists(requests).at(-1).params, 'project'), false);
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators', 'bob', 'alice', 'zoe']);
    });
});

test('the search narrows the options by name, ignoring case; All stays first', async () => {
    const { Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        const input = selector(view.container, 'annotator').querySelector('input[role="combobox"]');
        assert.equal(document.activeElement === input, true, 'the search field takes focus');
        await type(input, 'ZO');
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators', 'zoe']);
        await type(input, 'nobody');
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators']);
        assert.equal(statusLine(view.container, 'annotator'), 'No match for this search');
    });
});

test('picking an option sets the filter in the address as a card row does; All clears it', async () => {
    const { history, requests, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'project'));
        await view.settle();
        const option = [...selector(view.container, 'project').querySelectorAll('[role="option"]')]
            .find((element) => element.textContent === 'Retail shelves');
        await click(option);
        await view.settle();
        assert.equal(history.location.search, '?project=2&org=team-org&period=week');
        assert.equal(new URL(requests.filter((sent) => sent.endpoint === 'overview').at(-1).url, 'http://localhost')
            .searchParams.get('project'), '2');
        assert.equal(selector(view.container, 'project').querySelector('[role="listbox"]') === null, true, 'the dropdown closes');
        assert.match(button(view.container, 'project').textContent, /Retail shelves/);
        assert.equal(document.activeElement === button(view.container, 'project'), true, 'focus returns to the button');

        // the selected option is marked; All removes the filter
        await click(button(view.container, 'project'));
        await view.settle();
        const selected = selector(view.container, 'project').querySelector('[aria-selected="true"]');
        assert.equal(selected.textContent, 'Retail shelves');
        await click(selector(view.container, 'project').querySelector('.cvat-team-analytics-filter-option-all'));
        await view.settle();
        assert.equal(history.location.search, '?period=week');
    });
});

test('the clear button stays beside an active filter, outside the dropdown button', async () => {
    const { history, Page } = openPage({ search: '?annotator=11&org=team-org' });
    await opened(Page, async (view) => {
        const clear = selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-clear');
        assert.ok(clear);
        assert.equal(button(view.container, 'annotator').contains(clear), false);
        assert.equal(selector(view.container, 'project').querySelector('.cvat-team-analytics-filter-clear') === null, true);
        await click(clear);
        await view.settle();
        assert.equal(history.location.search, '?period=week');
    });
});

test('a period not processed yet offers only All and the current value, and says why', async () => {
    const withheld = { ...ANNOTATORS, processed: false, total: null, rows: null };
    const { Page } = openPage({ search: '?annotator=40&org=team-org', lists: () => ({ body: withheld }) });
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators', 'Annotator #40']);
        assert.equal(selector(view.container, 'annotator').querySelector('[aria-selected="true"]').textContent,
            'Annotator #40');
        assert.equal(statusLine(view.container, 'annotator'), 'This period is not processed yet');
    });
});

test('a failed list says so and is asked again on the next opening; a list that arrived is kept', async () => {
    let fail = true;
    const { requests, Page } = openPage({
        lists: (by) => (fail ? { status: 503, body: { error: 'unavailable' } } : { body: by === 'projects' ? PROJECTS : ANNOTATORS }),
    });
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.equal(statusLine(view.container, 'annotator'), 'Could not load the list');
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators']);
        await click(button(view.container, 'annotator'));

        fail = false;
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.equal(lists(requests).length, 2, 'asked again');
        assert.deepEqual(options(view.container, 'annotator'), ['All annotators', 'bob', 'alice', 'zoe']);
        await click(button(view.container, 'annotator'));
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.equal(lists(requests).length, 2, 'kept while the page is open');
    });
});

test('while the list loads the dropdown says so', async () => {
    let answer;
    const pending = new Promise((resolve) => { answer = resolve; });
    const { Page } = openPage({ lists: () => pending });
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.equal(statusLine(view.container, 'annotator'), 'Loading…');
        answer({ body: ANNOTATORS });
        await view.settle();
        assert.equal(statusLine(view.container, 'annotator'), '');
    });
});

test('another period asks its own options', async () => {
    const { requests, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        await click(button(view.container, 'annotator'));
        const twoWeeks = [...view.container.querySelectorAll('.cvat-team-analytics-period')]
            .find((element) => element.textContent === 'Two weeks');
        await click(twoWeeks);
        await view.settle();
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.deepEqual(lists(requests).map((sent) => sent.params.period), ['week', 'two_weeks']);
    });
});

test('a shared link\'s value that is not among the options is still shown as selected', async () => {
    const { Page } = openPage({ search: '?project=77&org=team-org' });
    await opened(Page, async (view) => {
        await click(button(view.container, 'project'));
        await view.settle();
        assert.deepEqual(options(view.container, 'project'),
            ['All projects', 'Project #77', 'Retail shelves', 'No project', 'Street scenes']);
        assert.equal(selector(view.container, 'project').querySelector('[aria-selected="true"]').textContent, 'Project #77');
    });
});

test('keyboard: ArrowDown opens, arrows move the active option, Enter picks, Escape closes back to the button', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        const trigger = button(view.container, 'annotator');
        trigger.focus();
        await press(trigger, 'ArrowDown');
        await view.settle();
        const input = selector(view.container, 'annotator').querySelector('input[role="combobox"]');
        assert.equal(document.activeElement === input, true);
        const listbox = selector(view.container, 'annotator').querySelector('[role="listbox"]');
        assert.equal(input.getAttribute('aria-controls'), listbox.id);
        assert.equal(trigger.getAttribute('aria-controls'), listbox.id);
        const activeName = () => document.getElementById(input.getAttribute('aria-activedescendant')).textContent;
        assert.equal(activeName(), 'All annotators', 'with no filter All is active');
        await press(input, 'ArrowDown');
        await press(input, 'ArrowDown');
        assert.equal(activeName(), 'alice');
        await press(input, 'ArrowUp');
        assert.equal(activeName(), 'bob');
        await press(input, 'Escape');
        assert.equal(selector(view.container, 'annotator').querySelector('[role="listbox"]') === null, true);
        assert.equal(trigger.getAttribute('aria-expanded'), 'false');
        assert.equal(document.activeElement === trigger, true);
        assert.equal(history.location.search, '', 'Escape picks nothing');

        await press(trigger, 'ArrowDown');
        await view.settle();
        const again = selector(view.container, 'annotator').querySelector('input[role="combobox"]');
        await press(again, 'ArrowDown');
        await press(again, 'ArrowDown');
        await press(again, 'ArrowDown');
        await press(again, 'Enter');
        await view.settle();
        assert.equal(history.location.search, '?annotator=40&org=team-org&period=week');
        assert.equal(document.activeElement === button(view.container, 'annotator'), true);
    });
});

test('clicking outside closes the dropdown', async () => {
    const { Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'project'));
        await view.settle();
        assert.ok(selector(view.container, 'project').querySelector('[role="listbox"]'));
        await act(async () => {
            document.body.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }));
        });
        assert.equal(selector(view.container, 'project').querySelector('[role="listbox"]') === null, true);
    });
});

test('a card row click still sets the filter, and the selector shows it', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        await click(view.container.querySelector('.cvat-team-analytics-annotator-row'));
        await view.settle();
        assert.equal(history.location.search, '?annotator=11&org=team-org&period=week');
        assert.match(button(view.container, 'annotator').textContent, /alice/);
    });
});

test('after typing, the first match is active and Enter picks it; with no match nothing is active', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        const input = selector(view.container, 'annotator').querySelector('input[role="combobox"]');
        const activeName = () => {
            const active = input.getAttribute('aria-activedescendant');
            return active ? document.getElementById(active).textContent : null;
        };
        await type(input, 'nobody');
        assert.equal(activeName(), null, 'no match: no active option');
        await press(input, 'Enter');
        assert.equal(history.location.search, '', 'Enter does nothing');
        assert.ok(selector(view.container, 'annotator').querySelector('[role="listbox"]'), 'still open');
        await type(input, 'ZO');
        assert.equal(activeName(), 'zoe', 'the first match, not All');
        await press(input, 'Enter');
        await view.settle();
        assert.equal(history.location.search, '?annotator=40&org=team-org&period=week');
    });
});

test('typing while the list loads makes the first match active once it arrives', async () => {
    let answer;
    const pending = new Promise((resolve) => { answer = resolve; });
    const { Page } = openPage({ lists: () => pending });
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        const input = selector(view.container, 'annotator').querySelector('input[role="combobox"]');
        await type(input, 'ali');
        answer({ body: ANNOTATORS });
        await view.settle();
        assert.equal(document.getElementById(input.getAttribute('aria-activedescendant')).textContent, 'alice');
    });
});

test('the clear button gives the focus to the selector\'s button', async () => {
    const { Page } = openPage({ search: '?annotator=11&org=team-org' });
    await opened(Page, async (view) => {
        const clear = selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-clear');
        clear.focus();
        await click(clear);
        await view.settle();
        assert.equal(selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-clear') === null, true);
        assert.equal(document.activeElement === button(view.container, 'annotator'), true);
    });
});

test('an open dropdown closes when the period or the organization changes under it', async () => {
    const { history, Page } = openPage();
    await opened(Page, async (view) => {
        await click(button(view.container, 'annotator'));
        await view.settle();
        assert.ok(selector(view.container, 'annotator').querySelector('[role="listbox"]'));
        await act(async () => { history.push('/team-analytics?period=two_weeks&org=team-org'); });
        await view.settle();
        assert.equal(selector(view.container, 'annotator').querySelector('[role="listbox"]') === null, true, 'closed');
        assert.equal(button(view.container, 'annotator').getAttribute('aria-expanded'), 'false');
        assert.equal(document.activeElement === button(view.container, 'annotator'), true, 'the focus was in it: back to the button');
        // a filter change keeps the options: an open dropdown stays open
        await click(button(view.container, 'annotator'));
        await view.settle();
        await act(async () => { history.push('/team-analytics?period=two_weeks&project=1&org=team-org'); });
        await view.settle();
        assert.ok(selector(view.container, 'annotator').querySelector('[role="listbox"]'), 'still open');
    });
});

const { placePopup, widestPopup } = loadPage('filter-select.tsx');

test('the popup is placed by the widest it becomes: 360px, or 90% of a narrow window, or its own width', () => {
    assert.equal(widestPopup(260, 1280), 360);
    assert.equal(widestPopup(260, 300), 270);
    assert.equal(widestPopup(420, 1280), 420, 'a box wider than 360px makes the popup as wide');
});

test('the popup is placed inside the page container', () => {
    const container = { left: 0, right: 1000 };
    assert.deepEqual(placePopup({ left: 100, right: 300 }, 360, container), { side: 'left' });
    assert.deepEqual(placePopup({ left: 800, right: 990 }, 360, container), { side: 'right' }, 'near the right edge');
    // a box too far right for a left-anchored popup and too far left for a right-anchored one: shifted to the
    // container's left edge, no wider than the container
    assert.deepEqual(placePopup({ left: 150, right: 300 }, 360, { left: 0, right: 400 }),
        { side: 'shifted', left: -150, maxWidth: 360 }, 'no wider than the popup may become');
    assert.deepEqual(placePopup({ left: 150, right: 300 }, 360, { left: 0, right: 300 }),
        { side: 'shifted', left: -150, maxWidth: 300 }, 'no wider than a narrow container');
    // a container wider than the popup may become, with neither edge fitting: the 360px cap holds
    assert.deepEqual(placePopup({ left: 210, right: 350 }, 360, { left: 0, right: 560 }),
        { side: 'shifted', left: -210, maxWidth: 360 });
});

test('opening near the right edge of the page anchors the popup to the box\'s right edge', async () => {
    const { Page } = openPage();
    const rects = {
        'cvat-team-analytics-page': { left: 0, right: 1000, width: 1000 },
        'cvat-team-analytics-filter-annotator': { left: 800, right: 990, width: 190 },
        'cvat-team-analytics-filter-project': { left: 32, right: 250, width: 218 },
        'cvat-team-analytics-filter-popup': { left: 799, right: 1159, width: 360 },
    };
    const original = window.HTMLElement.prototype.getBoundingClientRect;
    window.HTMLElement.prototype.getBoundingClientRect = function measured() {
        const found = Object.keys(rects).find((name) => this.classList.contains(name));
        return found ? { top: 0, bottom: 36, height: 36, ...rects[found] } : original.call(this);
    };
    try {
        await opened(Page, async (view) => {
            await click(button(view.container, 'annotator'));
            await view.settle();
            const popup = selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-popup');
            // the class sets `right: -1px; left: auto` (projects-filters.scss)
            assert.ok(popup.classList.contains('cvat-team-analytics-filter-popup-right'), popup.className);
            // the project selector at the left keeps the default placement
            await click(button(view.container, 'project'));
            await view.settle();
            const left = selector(view.container, 'project').querySelector('.cvat-team-analytics-filter-popup');
            assert.ok(left.classList.contains('cvat-team-analytics-filter-popup-left'), left.className);
            assert.equal(left.getAttribute('style'), null);
            // a narrow page: shifted to the container's left edge, no wider than the container
            Object.assign(rects, {
                'cvat-team-analytics-page': { left: 0, right: 400, width: 400 },
                'cvat-team-analytics-filter-annotator': { left: 150, right: 300, width: 150 },
            });
            // still open from before: closed, then opened again
            await click(button(view.container, 'annotator'));
            await click(button(view.container, 'annotator'));
            await view.settle();
            const shifted = selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-popup');
            assert.ok(shifted.classList.contains('cvat-team-analytics-filter-popup-shifted'), shifted.className);
            assert.equal(shifted.style.left, '-150px');
            // the 400px container is wider than the popup may become: the 360px cap holds
            assert.equal(shifted.style.maxWidth, '360px');

            // opened while its list loads, the popup is at its narrowest (260px); it is placed by the widest it
            // becomes (360px): a box that fits 260 but not 360 opens from its right edge
            Object.assign(rects, {
                'cvat-team-analytics-page': { left: 0, right: 1000, width: 1000 },
                'cvat-team-analytics-filter-annotator': { left: 700, right: 900, width: 200 },
                'cvat-team-analytics-filter-popup': { left: 699, right: 959, width: 260 },
            });
            await click(button(view.container, 'annotator'));
            await click(button(view.container, 'annotator'));
            await view.settle();
            const narrow = selector(view.container, 'annotator').querySelector('.cvat-team-analytics-filter-popup');
            assert.ok(narrow.classList.contains('cvat-team-analytics-filter-popup-right'), narrow.className);
        });
    } finally {
        window.HTMLElement.prototype.getBoundingClientRect = original;
    }
});
