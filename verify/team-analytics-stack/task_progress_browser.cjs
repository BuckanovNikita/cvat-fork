// Task progress on the tasks list in a real browser against the running stack
// (run.sh check-task-progress), after task_progress.py seed.
//
//   node task_progress_browser.cjs FILE    FILE is the JSON the seed printed
//
// The seeding account signs in through CVAT's login form into its personal workspace and opens
// the tasks list filtered to the seeded tasks. On each task card the summary widget must show,
// for every stage/state that holds jobs, the legend entry with its count, a segment whose
// computed colour is the specified one (docs/fork-specification.md, UI-2), whose flex weight is
// the count and whose tooltip names it, the task's total, and no "not available" bucket or other
// bucket; the upstream fallback labels must be absent. Every legend entry must be readable on the
// card (contrast at least 4.5:1 after compositing its colour onto the card's background); for the
// single annotation/new job this is the case of docs/evidence/2026-11-13-task-legend-verification.md.
//
// Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_BROWSER_BIN (google-chrome),
// TA_SCREENSHOT_DIR (optional: a PNG of the list).
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
    launch, openPage, check, log,
} = require('./browser_check.cjs');

const BASE = process.env.TA_BASE_URL;
const PASSWORD = process.env.TA_SEED_PASSWORD;

// The UI-2 table of the fork specification, as the browser computes the colours. Written out here
// rather than read from the product's palette, so a changed palette fails the check.
const COLORS = {
    annotation: {
        new: 'rgb(193, 193, 193)', 'in progress': 'rgb(250, 173, 20)', completed: 'rgb(250, 254, 1)', rejected: 'rgb(255, 65, 54)',
    },
    validation: {
        new: 'rgb(180, 218, 253)', 'in progress': 'rgb(24, 144, 255)', completed: 'rgb(0, 71, 138)', rejected: 'rgb(255, 65, 54)',
    },
    acceptance: {
        new: 'rgb(179, 255, 102)', 'in progress': 'rgb(179, 255, 102)', completed: 'rgb(97, 194, 0)', rejected: 'rgb(255, 65, 54)',
    },
};
const STAGES = ['annotation', 'validation', 'acceptance'];
const STATES = ['new', 'in progress', 'completed', 'rejected'];
const MIN_CONTRAST = 4.5;

async function signInPersonal(browser, username) {
    const page = await openPage(browser);
    await page.goto(`${BASE}/auth/login`);
    await page.evaluate('localStorage.removeItem("currentOrganization")');
    await page.type('#credential', username);
    await page.type('#password', PASSWORD);
    await page.evaluate('document.querySelector(".cvat-credentials-action-button").click()');
    await page.waitFor('location.pathname !== "/auth/login" && !!document.querySelector(".cvat-header")', `${username} signed in`);
    return page;
}

// What the tasks list shows for each task id, or null while a card or its summary is missing.
const READ_CARDS = (ids) => `(() => {
    const ids = ${JSON.stringify(ids)};
    const cards = [...document.querySelectorAll(".cvat-tasks-list-item")];
    const out = {};
    for (const id of ids) {
        const card = cards.find((c) => c.querySelector(".cvat-item-task-id")?.textContent.trim() === "#" + id + ":");
        if (!card || !card.querySelector(".cvat-task-item-jobs-progress")) return null;
        const wrapper = card.querySelector(".cvat-task-item-progress-wrapper");
        out[id] = {
            cardBackground: getComputedStyle(card).backgroundColor,
            legends: [...wrapper.querySelectorAll("[class*=cvat-jobs-legend-]")].map((e) => ({
                key: [...e.classList].find((c) => c.startsWith("cvat-jobs-legend-")).slice("cvat-jobs-legend-".length),
                text: e.textContent.trim(),
                color: getComputedStyle(e.querySelector("strong") || e).color,
            })),
            segments: [...wrapper.querySelectorAll(".cvat-task-item-jobs-progress-segment")].map((e) => ({
                key: [...e.classList].find((c) => c.startsWith("cvat-jobs-progress-")).slice("cvat-jobs-progress-".length),
                background: getComputedStyle(e).backgroundColor,
                flexGrow: getComputedStyle(e).flexGrow,
                title: e.getAttribute("title"),
            })),
            text: wrapper.textContent.replace(/\\s+/g, " ").trim(),
            fallback: !!wrapper.querySelector(".cvat-task-completed-progress, .cvat-task-validation-progress, .cvat-task-annotation-progress"),
        };
    }
    return out;
})()`;

function channels(css) {
    const values = /^rgba?\(/.test(css) ? css.match(/[\d.]+/g).map(Number) : [];
    check(values.length === 3 || values.length === 4, `not a computed rgb colour: "${css}"`);
    return values;
}

// WCAG contrast of a text colour, composited onto an opaque background.
function contrast(textCss, backgroundCss) {
    const [r, g, b, a = 1] = channels(textCss);
    const bg = channels(backgroundCss);
    const luminance = (rgb) => {
        const [lr, lg, lb] = rgb.map((v) => {
            const s = v / 255;
            return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
        return lr * 0.2126 + lg * 0.7152 + lb * 0.0722;
    };
    const text = [r, g, b].map((v, i) => v * a + bg[i] * (1 - a));
    const [hi, lo] = [luminance(text), luminance(bg.slice(0, 3))].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
}

function checkCard(task, card) {
    const counts = new Map();
    for (const { stage, state } of task.jobs) counts.set(`${stage}|${state}`, (counts.get(`${stage}|${state}`) || 0) + 1);
    const expected = STAGES.flatMap((stage) => STATES.map((state) => ({ stage, state })))
        .filter(({ stage, state }) => counts.has(`${stage}|${state}`))
        .map(({ stage, state }) => ({
            key: `${stage}-${state.replace(/ /g, '-')}`,
            label: `${stage} / ${state}`,
            count: counts.get(`${stage}|${state}`),
            color: COLORS[stage][state],
        }));
    const where = `task ${task.id}`;

    check(!card.fallback, `${where}: the upstream fallback labels are shown instead of the summary`);
    check(card.cardBackground === 'rgb(255, 255, 255)', `${where}: card background ${card.cardBackground}`);
    check(
        JSON.stringify(card.legends.map((l) => l.key)) === JSON.stringify(expected.map((e) => e.key)),
        `${where}: legend entries ${card.legends.map((l) => l.key)}, expected ${expected.map((e) => e.key)}`,
    );
    check(
        JSON.stringify(card.segments.map((s) => s.key)) === JSON.stringify(expected.map((e) => e.key)),
        `${where}: segments ${card.segments.map((s) => s.key)}, expected ${expected.map((e) => e.key)}`,
    );
    expected.forEach((want, i) => {
        const legend = card.legends[i];
        const segment = card.segments[i];
        check(legend.text === `• ${want.count} ${want.label}`, `${where}: legend "${legend.text}" for ${want.label}`);
        const ratio = contrast(legend.color, card.cardBackground);
        check(ratio >= MIN_CONTRAST, `${where}: ${want.label} legend ${legend.color} has contrast ${ratio.toFixed(2)}:1`);
        check(segment.background === want.color, `${where}: ${want.label} segment ${segment.background}, expected ${want.color}`);
        check(Number(segment.flexGrow) === want.count, `${where}: ${want.label} segment flex-grow ${segment.flexGrow}`);
        check(segment.title === `${want.count} ${want.label}`, `${where}: ${want.label} segment title "${segment.title}"`);
    });
    check(card.text.endsWith(`• ${task.jobs.length} total`), `${where}: card reads "${card.text}", expected the total ${task.jobs.length}`);
    check(!/not available/.test(card.text), `${where}: a "not available" bucket is shown`);
    const ratios = card.legends.map((l) => contrast(l.color, card.cardBackground));
    log(`task ${task.id}: ${expected.length} buckets as specified, total ${task.jobs.length}; `
        + `legend ${card.legends[0].color}, lowest contrast ${Math.min(...ratios).toFixed(2)}:1`);
}

async function main() {
    const seeded = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const ids = seeded.tasks.map((t) => t.id);
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-progress-browser-'));
    let browser;
    try {
        browser = await launch(profile);
        const page = await signInPersonal(browser, seeded.account);
        const filter = JSON.stringify({ or: ids.map((id) => ({ '==': [{ var: 'id' }, id] })) });
        await page.goto(`${BASE}/tasks?filter=${encodeURIComponent(filter)}`);
        const cards = await page.waitFor(READ_CARDS(ids), `the task cards of ${ids} with their summaries`);
        await page.screenshot('task-progress-list');
        for (const task of seeded.tasks) checkCard(task, cards[task.id]);
        log(`${seeded.account}: the tasks list shows the progress of tasks ${ids} as specified`);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

module.exports = { READ_CARDS, contrast, checkCard };

if (require.main === module) {
    main().catch((error) => {
        process.stderr.write(`task progress browser check failed: ${error.message}\n`);
        process.exit(1);
    });
}
