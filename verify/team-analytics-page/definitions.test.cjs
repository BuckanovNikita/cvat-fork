// Definitions: the overview ends with short definitions of the terms its figures use, worded from GLOSSARY.md,
// after the details table; a full view replaces the overview and shows none.
const assert = require('node:assert/strict');
const test = require('node:test');
const {
    React, dependency, loadPage, mount, suppliedService,
} = require('./helper.cjs');

const HOUR = 3600000;
const PERIOD = {
    name: 'week', first_day: '2026-11-07', last_day: '2026-11-13', month: null, to_date: false, unit: 'day',
};
const OVERVIEW = {
    period: PERIOD,
    by_annotator: { rows: [{ user_id: 11, user_name: 'alice', working_time_ms: 9 * HOUR }], rest: { count: 0, working_time_ms: 0 } },
    filters: { project: null, annotator: null },
    processed: true,
};
const DETAILS = {
    by: 'annotators', page: 1, page_size: 10, total: 0, legacy: false, shapes: 'bounding_boxes', processed: true,
    technical_accounts: 0, rows: [],
};
const LIST = {
    period: PERIOD, processed: true, by: 'annotators', legacy: false, shapes: 'bounding_boxes',
    total: { count: 0, working_time_ms: 0 }, rows: [],
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
        await check(view.container);
    } finally {
        await view.unmount();
    }
}

const definitions = (container) => container.querySelector('.cvat-team-analytics-definitions');

test('the overview ends with the definitions, after the details table, in the glossary wording', async () => {
    await opened('?period=week', (container) => {
        const overview = container.querySelector('.cvat-team-analytics-cards');
        assert.ok(overview, 'the overview is shown');
        const block = definitions(container);
        assert.ok(block, 'the definitions are on the overview');
        assert.equal(overview.lastElementChild, block, 'they end the overview');
        assert.ok(block.previousElementSibling.classList.contains('cvat-team-analytics-details'),
            'they follow the details table');
        const shown = [...block.querySelectorAll('.cvat-team-analytics-definition')].map((item) => [
            item.querySelector('.cvat-team-analytics-definition-term').textContent,
            item.textContent.slice(item.querySelector('.cvat-team-analytics-definition-term').textContent.length).trim(),
        ]);
        assert.deepEqual(shown, [
            ['Session.', 'One uninterrupted interval of job work by one person, at most a day long. A pause ' +
                'longer than five minutes ends it. Seen for a single project, a session counts if it touched ' +
                'that project, and its length is only the time spent inside it.'],
            ['Working time.', 'The time the server counts as worked, the same figure Grafana reports. It is the ' +
                'only total: every breakdown of time adds up to it.'],
            ['Time per operation.', "The time from a person's previous action to the end of the operation, so " +
                'that finding, deciding and pointing are part of it. A pause longer than 100 seconds before an ' +
                'action belongs to no operation.'],
            ['Model.', 'Created without a person drawing it: saved by a technical account or produced by the ' +
                'built-in detector. Model boxes have counts but no time.'],
        ]);
    });
});

test('a full view shows no definitions, for a chart and for a trend', async () => {
    await opened('?period=week', (container) => assert.ok(definitions(container), 'the overview has them'));
    for (const search of ['?period=week&view=annotators', '?period=week&view=trend-working_time']) {
        // eslint-disable-next-line no-await-in-loop
        await opened(search, (container) => {
            assert.ok(container.querySelector('.cvat-team-analytics-full'), `${search} opens a full view`);
            assert.equal(definitions(container), null, `${search} shows no definitions`);
        });
    }
});
