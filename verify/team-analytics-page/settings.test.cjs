// "Team Analytics settings": the Settings button of the page header and the modal that edits the instance's
// Technical accounts list (mounted page, supplied answers for the figures and for the settings).
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, act, dependency, loadCoreExceptions, loadPage, mount, render, suppliedService, suppliedSettings, text,
} = require('./helper.cjs');

const { createMemoryHistory } = dependency('history');
const HOUR = 3600000;

const OVERVIEW = {
    by_annotator: { rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 4 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    filters: { project: null, annotator: null },
};
const DETAILS = {
    by: 'annotators', page: 1, page_size: 10, total: 0, legacy: false, shapes: 'bounding_boxes', processed: true,
    technical_accounts: 0, rows: [],
};
const SETTINGS = {
    technical_accounts: [
        { user_id: 12, user_name: 'ta-bot', deleted: false },
        { user_id: 40, user_name: 'old-importer', deleted: true },
    ],
};
const USERS = [
    { id: 12, username: 'ta-bot', first_name: '', last_name: '' },
    { id: 51, username: 'ta-loader', first_name: 'Upload', last_name: 'Script' },
    { id: 52, username: 'tamara', first_name: '', last_name: '' },
];

function endpointOf(url) {
    return new URL(url, 'http://localhost').pathname.replace('/api/team-analytics/', '');
}

function openPage({ settings = () => ({ body: SETTINGS }), users = () => ({ body: { users: USERS } }) } = {}) {
    const history = createMemoryHistory({ initialEntries: ['/team-analytics'] });
    const figures = suppliedService((url) => {
        const endpoint = endpointOf(url);
        if (endpoint === 'settings/users') return users(url);
        if (endpoint === 'details') return { body: DETAILS };
        if (endpoint === 'list') {
            return { body: { by: 'annotators', legacy: false, shapes: 'all', total: { count: 0, working_time_ms: 0 }, rows: [] } };
        }
        if (endpoint === 'overview') return { body: OVERVIEW };
        return { body: {} };
    });
    const saved = suppliedSettings(settings);
    const Page = loadPage('team-analytics-page.tsx', {
        'react-redux': { useSelector: (select) => select({ organizations: { current: null } }) },
        'react-router': { useHistory: () => history },
        './service': {
            ...loadPage('service.ts'), requestService: figures.request, requestSettings: saved.request,
        },
        './project-names': { lookupProjectNames: async () => ({}) },
    }).default;
    return { figures: figures.requests, settings: saved.requests, Page };
}

async function opened(Page, check) {
    const view = await mount(React.createElement(Page));
    try {
        await view.settle();
        await check(view);
    } finally {
        await view.unmount();
        // a modal left open renders outside the page's container
        document.body.querySelectorAll('.ant-modal-root').forEach((element) => element.remove());
    }
}

async function click(element) {
    await act(async () => { element.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
}

async function wait(ms) {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)); });
}

async function type(input, value) {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await act(async () => {
        setter.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
}

const modal = () => {
    const found = document.body.querySelector('.cvat-team-analytics-settings-modal');
    return found && found.closest('.ant-modal-wrap')?.style.display !== 'none' ? found : null;
};
const rows = () => [...modal().querySelectorAll('.cvat-team-analytics-settings-account-name')].map((row) => row.textContent);
const endpoints = (requests) => requests.map((sent) => sent.endpoint);

async function openSettings(view) {
    await click(view.container.querySelector('.cvat-team-analytics-settings-button'));
    await view.settle();
}

// opens the picker, types `search` and waits for the debounced request
async function searchFor(view, search) {
    const picker = modal().querySelector('.cvat-team-analytics-settings-picker');
    await act(async () => {
        picker.querySelector('.ant-select-selector').dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }));
    });
    await type(picker.querySelector('input'), search);
    await wait(500);
    await view.settle();
}

const offered = () => [...document.body.querySelectorAll('.cvat-team-analytics-settings-picker-dropdown .ant-select-item-option')]
    .map((option) => option.textContent);

test('the header has a Settings button in the ready, loading and error states, not when refused', () => {
    const View = loadPage('team-analytics-view.tsx').default;
    const shown = (state) => /cvat-team-analytics-settings-button/.test(render(View, {
        organization: null, state, onOpenSettings() {},
    }));
    assert.equal(shown({ kind: 'ready', overview: OVERVIEW }), true);
    assert.equal(shown({ kind: 'loading' }), true);
    assert.equal(shown({ kind: 'error' }), true);
    assert.equal(shown({ kind: 'denied' }), false);
    assert.equal(shown({ kind: 'signed-out' }), false);
    const html = render(View, { organization: null, state: { kind: 'ready', overview: OVERVIEW }, onOpenSettings() {} });
    const header = html.match(/<div class="cvat-team-analytics-header">(.*?)<\/button><\/div>/)[1];
    assert.match(text(header), /Team analytics .* Settings$/, 'at the right of the title');
    assert.match(header, /anticon-setting/, 'with a gear');
});

test('the page loads nothing of the settings until the button is used; opening loads the list', async () => {
    const { settings, Page } = openPage();
    await opened(Page, async (view) => {
        assert.equal(settings.length, 0);
        assert.equal(modal() === null, true);
        await openSettings(view);
        assert.deepEqual(settings, [{ method: 'GET', body: undefined }]);
        assert.ok(modal(), 'the modal is open');
        assert.match(document.body.querySelector('.ant-modal-title').textContent, /^Team Analytics settings$/);
        assert.match(modal().textContent, /Technical accounts/);
        assert.match(modal().textContent, /A technical account is a user account that stands for an automated process/);
        assert.match(modal().textContent, /A change applies to every past period the next time the page is loaded\./);
        assert.deepEqual(rows(), ['ta-bot', 'deleted account, id 40'], 'a deleted account by its id');
        assert.ok(modal().querySelector('[aria-label="Remove deleted account, id 40"]'));
        const label = modal().querySelector('.cvat-team-analytics-settings-picker-label');
        assert.equal(document.getElementById(label.htmlFor)?.tagName, 'INPUT', 'the picker\'s label names its input');
    });
});

test('while the list loads the modal says so, and a failed load can be tried again', async () => {
    let answer = null;
    const { settings, Page } = openPage({
        settings: () => (answer ? answer() : new Promise(() => {})),
    });
    await opened(Page, async (view) => {
        await openSettings(view);
        assert.match(modal().querySelector('.cvat-team-analytics-settings-loading').textContent, /Loading…/);
        assert.ok(document.body.querySelector('.cvat-team-analytics-settings-save').disabled, 'nothing to save yet');
        await click(document.body.querySelector('.cvat-team-analytics-settings-cancel'));
        await view.settle();

        answer = () => ({ status: 503, body: { error: 'unavailable' } });
        await openSettings(view);
        assert.match(modal().querySelector('.cvat-team-analytics-settings-load-failed').textContent,
            /The settings could not be loaded\./);
        answer = () => ({ body: SETTINGS });
        await click(modal().querySelector('.cvat-team-analytics-settings-load-failed button'));
        await view.settle();
        assert.deepEqual(rows(), ['ta-bot', 'deleted account, id 40']);
        assert.equal(settings.filter((sent) => sent.method === 'GET').length, 3);
    });
});

test('the search asks the fork\'s user search; accounts on the list are shown disabled, marked, not offered', async () => {
    const { figures, Page } = openPage();
    await opened(Page, async (view) => {
        await openSettings(view);
        await searchFor(view, 'ta');
        const searches = figures.filter((sent) => sent.endpoint === 'settings/users');
        assert.deepEqual(searches.at(-1).params, { search: 'ta' });
        // the server's 20 are all shown: one already listed is there, marked
        assert.deepEqual(offered(), ['ta-bot already on the list', 'ta-loader (Upload Script)', 'tamara']);
        const listed = document.body.querySelector('.cvat-team-analytics-settings-picker-dropdown .ant-select-item-option');
        assert.ok(listed.classList.contains('ant-select-item-option-disabled'), listed.className);
        assert.equal(listed.querySelector('.cvat-team-analytics-settings-listed').textContent, 'already on the list');
        await click(listed);
        await view.settle();
        assert.deepEqual(rows(), ['ta-bot', 'deleted account, id 40'], 'choosing it adds nothing');
        // removed from the list, it is offered again
        await click(modal().querySelector('[aria-label="Remove ta-bot"]'));
        await searchFor(view, 'ta');
        assert.deepEqual(offered(), ['ta-bot', 'ta-loader (Upload Script)', 'tamara']);
    });
});

test('a failed user search says so, apart from a search without results; the text is limited to 150', async () => {
    let answer = () => ({ status: 503, body: { error: 'unavailable' } });
    const { figures, Page } = openPage({ users: () => answer() });
    const statusOf = () => document.body.querySelector('.cvat-team-analytics-settings-search-status')?.textContent;
    await opened(Page, async (view) => {
        await openSettings(view);
        await searchFor(view, 'ta');
        assert.equal(statusOf(), 'The search could not be completed.', 'a 503');
        assert.deepEqual(offered(), []);
        answer = () => new Error('Network Error');
        await searchFor(view, 'tam');
        assert.equal(statusOf(), 'The search could not be completed.', 'no answer at all');
        answer = () => ({ status: 400, body: { error: 'bad_request', detail: 'too long' } });
        await searchFor(view, 'tama');
        assert.equal(statusOf(), 'The search could not be completed.', 'a 400');
        answer = () => ({ body: { users: [] } });
        await searchFor(view, 'nobody');
        assert.equal(statusOf(), 'No users found');

        await searchFor(view, 'x'.repeat(160));
        assert.equal(figures.filter((sent) => sent.endpoint === 'settings/users').at(-1).params.search, 'x'.repeat(150));
        assert.equal(modal().querySelector('.cvat-team-analytics-settings-picker input').value.length, 150);
    });
});

test('while a save is on its way the modal stays open and a second Save sends nothing', async () => {
    let finish;
    const { figures, settings, Page } = openPage({
        settings: (sent) => (sent.method === 'PUT' ?
            new Promise((resolve) => { finish = () => resolve({ body: SETTINGS }); }) : { body: SETTINGS }),
    });
    await opened(Page, async (view) => {
        await openSettings(view);
        const save = () => document.body.querySelector('.cvat-team-analytics-settings-save');
        // a double click: both before the button can render its loading state, so only the modal's own guard
        // can stop the second
        await act(async () => {
            save().dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
            save().dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
        });
        await view.settle();
        await click(document.body.querySelector('.cvat-team-analytics-settings-cancel'));
        await click(document.body.querySelector('.ant-modal-close'));
        await act(async () => {
            document.body.querySelector('.ant-modal-wrap').dispatchEvent(
                new window.KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, bubbles: true }),
            );
        });
        await view.settle();
        assert.ok(modal(), 'Cancel, the close button and Escape do nothing during the save');
        assert.equal(settings.filter((sent) => sent.method === 'PUT').length, 1, 'one save');
        const before = figures.length;
        await act(async () => { finish(); });
        await view.settle();
        assert.equal(modal() === null, true, 'closed once the save is answered');
        assert.ok(endpoints(figures.slice(before)).includes('overview'), 'and the figures reload');
    });
});

test('a save answered after its modal was closed and opened again changes nothing in the new one', async () => {
    const finish = [];
    const saved = suppliedSettings((sent) => (sent.method === 'PUT' ?
        new Promise((resolve) => { finish.push(resolve); }) : { body: SETTINGS }));
    const SettingsModal = loadPage('settings-modal.tsx', {
        './service': { ...loadPage('service.ts'), requestSettings: saved.request },
    }).default;
    let setOpen;
    let savedCount = 0;
    function Host() {
        const [open, change] = React.useState(true);
        setOpen = change;
        return React.createElement(SettingsModal, { open, onClose() {}, onSaved() { savedCount += 1; } });
    }
    const view = await mount(React.createElement(Host));
    try {
        await view.settle();
        await act(async () => {
            const save = document.body.querySelector('.cvat-team-analytics-settings-save');
            save.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
            save.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
        });
        assert.equal(finish.length, 1, 'a double click saves once');
        // closed from outside (a refusal of another request) and opened again
        await act(async () => { setOpen(false); });
        await act(async () => { setOpen(true); });
        await view.settle();
        await act(async () => { finish[0]({ status: 400, body: null, message: 'An old failure.' }); });
        await view.settle();
        assert.equal(document.body.querySelector('.cvat-team-analytics-settings-error') === null, true, 'no old error');
        assert.equal(document.body.querySelector('.cvat-team-analytics-settings-save').classList.contains('ant-btn-loading'),
            false, 'not saving');
        // the new opening saves on its own
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await view.settle();
        assert.equal(finish.length, 2, 'one save per opening');
        await act(async () => { finish[1]({ body: SETTINGS }); });
        await view.settle();
        assert.equal(savedCount, 1);
    } finally {
        await view.unmount();
        document.body.querySelectorAll('.ant-modal-root').forEach((element) => element.remove());
    }
});

test('removing and adding, then Save, sends the whole list of ids; the modal closes and the figures reload', async () => {
    const { figures, settings, Page } = openPage({
        settings: (sent) => (sent.method === 'PUT' ? {
            body: { technical_accounts: [{ user_id: 51, user_name: 'ta-loader', deleted: false },
                { user_id: 40, user_name: 'old-importer', deleted: true }] },
        } : { body: SETTINGS }),
    });
    await opened(Page, async (view) => {
        await openSettings(view);
        await click(modal().querySelector('[aria-label="Remove ta-bot"]'));
        assert.deepEqual(rows(), ['deleted account, id 40']);
        await searchFor(view, 'loader');
        const option = [...document.body.querySelectorAll('.cvat-team-analytics-settings-picker-dropdown .ant-select-item-option')]
            .find((element) => element.textContent.startsWith('ta-loader'));
        await click(option);
        await view.settle();
        assert.deepEqual(rows(), ['deleted account, id 40', 'ta-loader']);

        const before = figures.length;
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await view.settle();
        assert.deepEqual(settings.at(-1), { method: 'PUT', body: { technical_accounts: [40, 51] } });
        assert.equal(modal() === null, true, 'the modal closes');
        const reloaded = endpoints(figures.slice(before));
        for (const endpoint of ['overview', 'details', 'trends']) {
            assert.ok(reloaded.includes(endpoint), `${endpoint} is asked again: ${reloaded}`);
        }
    });
});

test('a save drops the selectors\' options kept in memory, so they are asked again', async () => {
    const { figures, Page } = openPage();
    await opened(Page, async (view) => {
        const selector = () => view.container.querySelector('.cvat-team-analytics-filter-annotator .cvat-team-analytics-filter-button');
        await click(selector());
        await view.settle();
        await click(selector());
        await click(selector());
        await view.settle();
        assert.equal(figures.filter((sent) => sent.endpoint === 'list').length, 1, 'kept while nothing changed');
        await click(selector());

        await openSettings(view);
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await view.settle();
        await click(selector());
        await view.settle();
        assert.equal(figures.filter((sent) => sent.endpoint === 'list').length, 2, 'asked again after the save');
    });
});

test('a failed save keeps the modal open with the reason; nothing is reloaded', async () => {
    const { figures, settings, Page } = openPage({
        settings: (sent) => (sent.method === 'PUT' ?
            { status: 400, body: null, message: 'User 99 does not exist.' } : { body: SETTINGS }),
    });
    await opened(Page, async (view) => {
        await openSettings(view);
        await click(modal().querySelector('[aria-label="Remove ta-bot"]'));
        const before = figures.length;
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await view.settle();
        assert.equal(settings.at(-1).method, 'PUT');
        assert.ok(modal(), 'still open');
        assert.equal(modal().querySelector('.cvat-team-analytics-settings-error').textContent, 'User 99 does not exist.');
        assert.equal(modal().querySelector('.cvat-team-analytics-settings-error').getAttribute('role'), 'alert');
        assert.deepEqual(rows(), ['deleted account, id 40'], 'the edit is kept');
        assert.equal(figures.filter((sent) => sent.endpoint === 'overview').length,
            figures.slice(0, before).filter((sent) => sent.endpoint === 'overview').length);
    });
});

test('Cancel sends nothing and leaves the list as it was', async () => {
    const { settings, Page } = openPage();
    await opened(Page, async (view) => {
        await openSettings(view);
        await click(modal().querySelector('[aria-label="Remove ta-bot"]'));
        await click(document.body.querySelector('.cvat-team-analytics-settings-cancel'));
        await view.settle();
        assert.equal(modal() === null, true);
        assert.deepEqual(settings.map((sent) => sent.method), ['GET']);
        await openSettings(view);
        assert.deepEqual(rows(), ['ta-bot', 'deleted account, id 40'], 'opened again from the server\'s list');
    });
});

test('a refusal while the modal is open closes it: a 401 on the settings, a 403 on the user search', async () => {
    const signedOut = openPage({ settings: () => ({ status: 401, body: null }) });
    await opened(signedOut.Page, async (view) => {
        await openSettings(view);
        assert.equal(modal() === null, true, 'closed');
        assert.ok(view.container.querySelector('.cvat-team-analytics-signed-out'));
    });
    const refused = openPage({ users: () => ({ status: 403, body: null }) });
    await opened(refused.Page, async (view) => {
        await openSettings(view);
        assert.ok(modal(), 'open with its list');
        await searchFor(view, 'ta');
        assert.equal(modal() === null, true, 'closed');
        assert.ok(view.container.querySelector('.cvat-team-analytics-denied'));
    });
});

test('a refused settings read and a refused user search are asked once, even with the modal left open', async () => {
    // the modal alone, without the page that would close it on the refusal
    let settingsAnswer = () => ({ status: 401, body: null });
    const figures = suppliedService(() => ({ status: 403, body: null }));
    const saved = suppliedSettings(() => settingsAnswer());
    const SettingsModal = loadPage('settings-modal.tsx', {
        './service': { ...loadPage('service.ts'), requestService: figures.request, requestSettings: saved.request },
    }).default;
    let setOpen;
    function Host() {
        const [open, change] = React.useState(true);
        setOpen = change;
        return React.createElement(SettingsModal, { open, onClose() {}, onSaved() {} });
    }
    const reads = () => saved.requests.filter((sent) => sent.method === 'GET').length;
    const view = await mount(React.createElement(Host));
    try {
        await view.settle();
        await wait(300);
        await view.settle();
        assert.equal(reads(), 1, 'a refused read is asked once');
        await act(async () => { setOpen(false); });
        await view.settle();
        await act(async () => { setOpen(true); });
        await view.settle();
        await wait(300);
        assert.equal(reads(), 2, 'opening again asks once more');

        settingsAnswer = () => ({ body: SETTINGS });
        await act(async () => { setOpen(false); });
        await act(async () => { setOpen(true); });
        await view.settle();
        await searchFor(view, 'ta');
        await wait(600);
        await view.settle();
        assert.deepEqual(endpoints(figures.requests), ['settings/users'], 'a refused search is asked once');
        assert.equal(reads(), 3);
    } finally {
        await view.unmount();
        document.body.querySelectorAll('.ant-modal-root').forEach((element) => element.remove());
    }
});

// --- the service functions and the real boundary -------------------------------------------------------------

const service = loadPage('service.ts');

// a failure after which the list may have been saved (no answer, or the 503 of a save whose older answers
// could not be retired) does not claim that nothing was saved
const UNFINISHED = 'The save did not finish, so the list may not have changed. Open the settings again to see the ' +
    'saved list.';

test('saveSettings says each failure in a sentence', async () => {
    const cases = [
        [{ status: 400, body: null, message: 'Too many technical accounts.' }, 'Too many technical accounts.'],
        [{ status: 403, body: null }, 'Only administrators can change Team Analytics settings.'],
        [{ status: 503, body: { error: 'unavailable' } }, UNFINISHED],
        [new Error('Network Error'), UNFINISHED],
    ];
    for (const [answer, error] of cases) {
        const { request } = suppliedSettings(() => answer);
        // eslint-disable-next-line no-await-in-loop
        assert.deepEqual(await service.saveSettings([1], request), { kind: 'failed', error });
    }
});

test('the real boundary reads and replaces the settings through cvat-core, with the 400 sentence kept', async () => {
    const { ServerError } = loadCoreExceptions();
    const calls = [];
    let next = () => ({ status: 200, data: SETTINGS });
    const core = {
        config: { backendAPI: '/api' },
        server: {
            async request(url, data) {
                calls.push({ url, data });
                const outcome = next();
                if (outcome instanceof Error) throw outcome;
                return outcome;
            },
        },
    };
    const real = loadPage('service.ts', { 'cvat-core-wrapper': { getCore: () => core, ServerError } });

    assert.deepEqual(await real.loadSettings(), SETTINGS);
    assert.deepEqual(await real.saveSettings([12, 40]), { kind: 'saved', settings: SETTINGS });
    assert.deepEqual(calls, [
        { url: '/api/team-analytics/settings', data: { method: 'GET' } },
        { url: '/api/team-analytics/settings', data: { method: 'PUT', data: { technical_accounts: [12, 40] } } },
    ]);

    // cvat-core turns {"error": "bad_request", "detail": "<sentence>"} into an error whose message is the sentence
    next = () => new ServerError('An account that is not on the list must be an existing user.', 400, 'Bad Request');
    assert.deepEqual(await real.saveSettings([99]),
        { kind: 'failed', error: 'An account that is not on the list must be an existing user.' });
    next = () => new ServerError('The CVAT server is unavailable', 0, 'ERR_NETWORK');
    assert.equal((await real.saveSettings([99])).kind, 'failed');
    assert.equal(await real.loadSettings(), null);
});

test('searchUsers asks GET settings/users with the text and reads the users', async () => {
    const { request, requests } = suppliedService(() => ({ body: { users: USERS } }));
    assert.deepEqual(await service.searchUsers('ta', request), USERS);
    assert.deepEqual(requests.map((sent) => [sent.endpoint, sent.params]), [['settings/users', { search: 'ta' }]]);
    const failed = suppliedService(() => ({ status: 400, body: { error: 'bad_request', detail: 'too long' } }));
    assert.equal(await service.searchUsers('x'.repeat(151), failed.request), null);
});

// --- a save that does not answer in time ------------------------------------------------------------------------

// the modal alone with a short save time limit; `answerPut(sent)` answers each PUT (a promise that may never settle)
async function withModal(answerPut, check) {
    const saved = suppliedSettings((sent) => (sent.method === 'PUT' ? answerPut(sent) : { body: SETTINGS }));
    const SettingsModal = loadPage('settings-modal.tsx', {
        './service': { ...loadPage('service.ts'), requestSettings: saved.request },
    }).default;
    const calls = { closed: 0, saved: 0 };
    let setOpen;
    function Host() {
        const [open, change] = React.useState(true);
        setOpen = change;
        return React.createElement(SettingsModal, {
            open,
            saveTimeLimitMs: 100,
            onClose() { calls.closed += 1; },
            onSaved() { calls.saved += 1; },
        });
    }
    const view = await mount(React.createElement(Host));
    try {
        await view.settle();
        await check({ view, calls, puts: () => saved.requests.filter((sent) => sent.method === 'PUT').length, setOpen: (open) => setOpen(open) });
    } finally {
        await view.unmount();
        document.body.querySelectorAll('.ant-modal-root').forEach((element) => element.remove());
    }
}

const errorText = () => document.body.querySelector('.cvat-team-analytics-settings-error')?.textContent ?? null;
const saveLoading = () => document.body.querySelector('.cvat-team-analytics-settings-save').classList.contains('ant-btn-loading');

test('a save that never answers stops being waited for after the limit, says so, and the modal can be closed', async () => {
    await withModal(() => new Promise(() => {}), async ({ view, calls, puts }) => {
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await click(document.body.querySelector('.cvat-team-analytics-settings-cancel'));
        assert.equal(calls.closed, 0, 'locked while the save is waited for');
        await wait(150);
        await view.settle();
        assert.equal(errorText(), UNFINISHED);
        assert.equal(saveLoading(), false, 'no longer saving');
        await click(document.body.querySelector('.cvat-team-analytics-settings-cancel'));
        assert.equal(calls.closed, 1, 'Cancel works again');
        await click(document.body.querySelector('.ant-modal-close'));
        assert.equal(calls.closed, 2, 'and the close button');
        assert.equal(puts(), 1);
    });
});

test('a save answered within the limit behaves as before', async () => {
    await withModal(() => new Promise((resolve) => { setTimeout(() => resolve({ body: SETTINGS }), 30); }),
        async ({ view, calls }) => {
            await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
            await wait(200);
            await view.settle();
            assert.equal(calls.saved, 1);
            assert.equal(errorText(), null, 'no time-limit message afterwards');
        });
});

test('a success that arrives after the limit neither closes a reopened modal nor reloads', async () => {
    const answers = [];
    await withModal(() => new Promise((resolve) => { answers.push(resolve); }), async ({
        view, calls, setOpen,
    }) => {
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await wait(150);
        await view.settle();
        assert.equal(errorText(), UNFINISHED);
        // the late success while the modal still shows the message
        await act(async () => { answers[0]({ body: SETTINGS }); });
        await view.settle();
        assert.equal(calls.saved, 0, 'no reload from the save given up on');
        assert.equal(errorText(), UNFINISHED, 'the message stays');
        // opened again, a second save is waited for on its own; the first save's answer has no part in it
        await act(async () => { setOpen(false); });
        await act(async () => { setOpen(true); });
        await view.settle();
        assert.equal(errorText(), null);
        await click(document.body.querySelector('.cvat-team-analytics-settings-save'));
        await act(async () => { answers[1]({ body: SETTINGS }); });
        await view.settle();
        assert.equal(calls.saved, 1, 'one reload, from the save answered in time');
    });
});
