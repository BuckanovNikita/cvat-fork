// The defect fixes in a real browser against the running stack (run.sh check-fixes; ticket 27 of the defect
// fixes). Headless Chrome over the DevTools protocol, with the helpers of browser_check.cjs.
//
//   node fixes_browser.cjs gestures STATE   ta-worker-c in the job fixes_run.py prepare-gestures made: draws a
//                                           box, undoes and redoes it (header buttons), draws two more and
//                                           saves; selects those two with the selection region (Shift and a
//                                           drag on the background) and moves the selection by its header
//                                           label; copies and pastes the selection and drags the pasted pair
//                                           by its first box; clears the selection, drags one box alone,
//                                           saves; holds F while the frame data requests are held back; at
//                                           the last frame (typed into the frame field) presses F once;
//                                           presses the slider near its start; leaves the job. Writes what it
//                                           did into STATE ("did") for fixes_run.py check-gestures.
//   node fixes_browser.cjs look ORG [split] the overview of ORG at 1400 px and at 400 px: the split bars of the
//                                           two working-time cards (with split, some row of each in several
//                                           parts) and the definitions block, judged from the page's layout;
//                                           full-page screenshots for the comparison with the prototype,
//                                           which a person makes.
//
// Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_BROWSER_BIN, TA_SCREENSHOT_DIR (required for look; keep it
// outside the repository).
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
    launch, signIn, check, sleep, log,
} = require('./browser_check.cjs');

const BASE = process.env.TA_BASE_URL;
const SHOTS = process.env.TA_SCREENSHOT_DIR || '';
const LATENCY_MS = 1500; // each request for frame data is held back this long while F is held
const HOLD_MS = 4000;
const REPEAT_MS = 50; // a held key's auto-repeat

// ---------------------------------------------------------------- input

const KEYS = {
    Control: { code: 'ControlLeft', keyCode: 17 },
    Shift: { code: 'ShiftLeft', keyCode: 16 },
    Enter: { code: 'Enter', keyCode: 13, text: '\r' },
};
const SHIFT = 8;

function keyInfo(key) {
    if (KEYS[key]) return { key, ...KEYS[key] };
    if (/^[a-z]$/.test(key)) return { key, code: `Key${key.toUpperCase()}`, keyCode: key.toUpperCase().charCodeAt(0), text: key };
    throw new Error(`unknown key ${key}`);
}

function input(page) {
    const send = (method, params) => page.send(method, params);
    const mouse = (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', ...extra });
    const move = async (x, y) => { await mouse('mouseMoved', x, y, { button: 'none' }); await sleep(250); };
    const click = async (x, y) => {
        await move(x, y);
        await mouse('mousePressed', x, y, { clickCount: 1, buttons: 1 });
        await mouse('mouseReleased', x, y, { clickCount: 1 });
        await sleep(400);
    };
    const keyEvent = (type, info, modifiers = 0, extra = {}) => send('Input.dispatchKeyEvent', {
        type, key: info.key, code: info.code, windowsVirtualKeyCode: info.keyCode, nativeVirtualKeyCode: info.keyCode,
        modifiers, ...extra,
    });
    // a drag; with shift, Shift is held down through it (the selection region)
    const drag = async (x, y, dx, dy, { shift = false } = {}) => {
        const modifiers = shift ? SHIFT : 0;
        await move(x, y);
        if (shift) await keyEvent('rawKeyDown', keyInfo('Shift'), SHIFT);
        await mouse('mousePressed', x, y, { clickCount: 1, buttons: 1, modifiers });
        for (let i = 1; i <= 8; i++) {
            await mouse('mouseMoved', x + (dx * i) / 8, y + (dy * i) / 8, { buttons: 1, modifiers });
            await sleep(40);
        }
        await mouse('mouseReleased', x + dx, y + dy, { clickCount: 1, modifiers });
        if (shift) await keyEvent('keyUp', keyInfo('Shift'));
        await sleep(800);
    };
    const press = async (key, { ctrl = false } = {}) => {
        const info = keyInfo(key);
        const modifiers = ctrl ? 2 : 0;
        if (ctrl) await keyEvent('rawKeyDown', keyInfo('Control'), 2);
        await keyEvent(info.text && !ctrl ? 'keyDown' : 'rawKeyDown', info, modifiers,
            info.text && !ctrl ? { text: info.text, unmodifiedText: info.text } : {});
        await keyEvent('keyUp', info, modifiers);
        if (ctrl) await keyEvent('keyUp', keyInfo('Control'));
        await sleep(600);
    };
    // a key held for `ms`: one key-down, then auto-repeated key-downs every `every` ms, then the key-up;
    // returns the number of key-down events sent
    const hold = async (key, ms, every) => {
        const info = keyInfo(key);
        const text = { text: info.text, unmodifiedText: info.text };
        await keyEvent('keyDown', info, 0, { ...text, autoRepeat: false });
        let downs = 1;
        const until = Date.now() + ms;
        while (Date.now() < until) {
            await sleep(every);
            await keyEvent('keyDown', info, 0, { ...text, autoRepeat: true });
            downs += 1;
        }
        await keyEvent('keyUp', info);
        return downs;
    };
    return {
        move, click, drag, press, hold,
    };
}

const rectOf = (page, selector) => page.evaluate(`(() => {
    const e = document.querySelector(${JSON.stringify(selector)});
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
})()`);

// the shapes on the canvas, left to right
const shapes = (page) => page.evaluate(`[...document.querySelectorAll(".cvat_canvas_shape")].map((e) => {
    const r = e.getBoundingClientRect();
    return { id: e.id, x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
}).sort((a, b) => a.x - b.x)`);
const shapeCount = (page) => page.evaluate('document.querySelectorAll(".cvat_canvas_shape").length');
const shownFrame = (page) => page.evaluate(
    'Number(document.querySelector(".cvat-player-slider .ant-slider-handle")?.getAttribute("aria-valuenow"))',
);

// the status of every POST /api/events the page makes
function watchEventPosts(browser, page) {
    const posts = [];
    const requests = new Set();
    browser.listeners.add((message) => {
        if (message.sessionId !== page.sessionId) return;
        if (message.method === 'Network.requestWillBeSent' && message.params.request.method === 'POST'
            && new URL(message.params.request.url).pathname === '/api/events') {
            requests.add(message.params.requestId);
        }
        if (message.method === 'Network.responseReceived' && requests.has(message.params.requestId)) {
            posts.push({ status: message.params.response.status });
        }
    });
    return posts;
}

async function openJob(page, job) {
    await page.goto(`${BASE}/tasks/${job.task_id}/jobs/${job.job_id}`);
    await page.waitFor('!!document.querySelector("#cvat_canvas_background") && document.querySelector("#cvat_canvas_background").getBoundingClientRect().width > 0', 'the annotation canvas', 90000);
    await sleep(2500);
}

async function drawRectangle(page, keys, from, to) {
    await page.evaluate('document.querySelector(".cvat-draw-rectangle-control").dispatchEvent(new MouseEvent("mouseover", {bubbles: true}))');
    const control = await rectOf(page, '.cvat-draw-rectangle-control');
    await keys.click(control.cx, control.cy);
    await page.waitFor('!!document.querySelector(".cvat-draw-rectangle-shape-button")', 'the draw popover');
    const button = await rectOf(page, '.cvat-draw-rectangle-shape-button');
    await keys.click(button.cx, button.cy);
    const before = await shapeCount(page);
    await keys.click(from.x, from.y);
    await keys.click(to.x, to.y);
    await page.waitFor(`document.querySelectorAll(".cvat_canvas_shape").length === ${before + 1}`, 'the rectangle drawn');
}

async function save(page, keys, bg, job, did) {
    await keys.move(bg.x - 150, bg.y + 20);
    await keys.press('s', { ctrl: true });
    did.hotkeys.SAVE_JOB = (did.hotkeys.SAVE_JOB || 0) + 1;
    const want = await shapeCount(page);
    await page.waitFor(`fetch("/api/jobs/${job.job_id}/annotations").then((r) => r.json()).then((j) => j.shapes.length === ${want})`, 'the saved annotations');
}

const moved = (a, b) => Math.abs(a.cx - b.cx) > 2 || Math.abs(a.cy - b.cy) > 2;

async function gestures(stateFile) {
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    const { job } = state;
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-fixes-'));
    let browser;
    const did = { drawn: 0, hotkeys: {} };
    try {
        browser = await launch(profile);
        const page = await signIn(browser, state.worker, state.org);
        await page.send('Network.enable', {});
        const posts = watchEventPosts(browser, page);
        await openJob(page, job);
        const keys = input(page);
        const bg = await rectOf(page, '#cvat_canvas_background');
        const at = (fx, fy) => ({ x: bg.x + bg.w * fx, y: bg.y + bg.h * fy });

        // draw, undo, redo: the redo restores the box and is no second creation
        await drawRectangle(page, keys, at(0.04, 0.08), at(0.3, 0.38));
        did.drawn += 1;
        const undo = await rectOf(page, '.cvat-annotation-header-undo-button');
        await keys.click(undo.cx, undo.cy);
        await page.waitFor('document.querySelectorAll(".cvat_canvas_shape").length === 0', 'the undone box gone');
        const redo = await rectOf(page, '.cvat-annotation-header-redo-button');
        await keys.click(redo.cx, redo.cy);
        await page.waitFor('document.querySelectorAll(".cvat_canvas_shape").length === 1', 'the redone box back');
        log('drew a box, undid it and redid it with the header buttons');

        // two more boxes with a gap between them, saved, so that CVAT's own drag records carry obj_id
        await drawRectangle(page, keys, at(0.38, 0.12), at(0.62, 0.42));
        await drawRectangle(page, keys, at(0.72, 0.12), at(0.96, 0.42));
        did.drawn += 2;
        await save(page, keys, bg, job, did);
        log('drew two more boxes and saved');

        // the selection region around the two right-hand boxes: Shift and a drag on the background
        const from = at(0.34, 0.04);
        const to = at(0.99, 0.5);
        await keys.drag(from.x, from.y, to.x - from.x, to.y - from.y, { shift: true });
        await page.waitFor('!!document.querySelector(".cvat_canvas_selected_objects_box")', 'the selection box');

        // Right after a region selection the canvas is in its selecting mode: the selection box lets presses
        // through to the canvas, a press on a member clears the selection, and the selection moves by its
        // header label (canvasView.ts). Move it by the label: both boxes follow (one group record).
        const byId = async () => Object.fromEntries((await shapes(page)).map((s) => [s.id.replace('cvat_canvas_shape_', ''), s]));
        let before = await byId();
        const label = await rectOf(page, '.cvat_canvas_selected_objects_label');
        check(!!label, 'the selection has no header label');
        await keys.drag(label.x + 10, label.cy, 0, bg.h * 0.08);
        let after = await byId();
        check(moved(after[2], before[2]) && moved(after[3], before[3]) && !moved(after[1], before[1]),
            `move of the selection by its label: ${JSON.stringify({ before, after })}`);
        log('moved the selection of two boxes by its header label; both moved');

        // copy and paste the selection: the pasted pair stays selected with the canvas idle, so a press inside
        // it drags the pair (the canvas decides whether as a member's drag or as the selection box's)
        await keys.press('c', { ctrl: true });
        await keys.press('v', { ctrl: true });
        const place = at(0.55, 0.72);
        await keys.click(place.x, place.y);
        await page.waitFor('document.querySelectorAll(".cvat_canvas_shape_selected_object").length === 2 && document.querySelectorAll(".cvat_canvas_shape").length === 5', 'the pasted pair, selected');
        did.pasted = 2;
        before = await byId();
        await keys.drag(before[4].cx, before[4].cy, 0, -bg.h * 0.1);
        after = await byId();
        check(moved(after[4], before[4]) && moved(after[5], before[5]) && !moved(after[2], before[2]),
            `drag inside the pasted selection: ${JSON.stringify({ before, after })}`);
        log('pasted the pair and dragged it by its first box; both moved');

        // clear the selection with a click on the background, then drag the first box alone
        const empty = at(0.12, 0.55);
        await keys.click(empty.x, empty.y);
        await page.waitFor('!document.querySelector(".cvat_canvas_selected_objects_box")', 'the selection cleared', 10000);
        before = await byId();
        await keys.drag(before[1].cx, before[1].cy, bg.w * 0.03, 0);
        after = await byId();
        check(moved(after[1], before[1]) && !moved(after[2], before[2]), `single drag: ${JSON.stringify({ before, after })}`);
        await save(page, keys, bg, job, did);
        log('dragged the first box alone and saved');
        await page.screenshot('fixes-gestures');

        // F held on slow frames: one NEXT_FRAME for each frame shown, none for repeats while a frame loads
        await keys.move(bg.x - 150, bg.y + 20);
        const start = await shownFrame(page);
        check(start === 0, `the job opened on frame ${start}`);
        await page.evaluate(`(() => {
            const shown = () => Number(document.querySelector(".cvat-player-slider .ant-slider-handle")?.getAttribute("aria-valuenow"));
            window.__taFrames = [shown()];
            let last = window.__taFrames[0];
            window.__taRecorder = setInterval(() => {
                const v = shown();
                if (v !== last) { window.__taFrames.push(v); last = v; }
            }, 10);
        })()`);
        // The frame data comes in chunks fetched by the UI's workers, which page-level network emulation does not
        // reach; the browser's own interception holds each chunk request back by LATENCY_MS instead.
        const delayed = [];
        const holdBack = (message) => {
            if (message.method !== 'Fetch.requestPaused') return;
            const { requestId, request } = message.params;
            delayed.push(new URL(request.url).searchParams.get('index'));
            setTimeout(() => browser.send('Fetch.continueRequest', { requestId }).catch(() => {}), LATENCY_MS);
        };
        browser.listeners.add(holdBack);
        await browser.send('Fetch.enable', { patterns: [{ urlPattern: '*type=chunk*', requestStage: 'Request' }] });
        const keydowns = await keys.hold('f', HOLD_MS, REPEAT_MS);
        await sleep(LATENCY_MS * 4 + 2000); // requests still on their way finish (and may show a frame)
        await browser.send('Fetch.disable');
        browser.listeners.delete(holdBack);
        await sleep(1000);
        const frames = await page.evaluate('(() => { clearInterval(window.__taRecorder); return window.__taFrames; })()');
        const changes = frames.length - 1;
        const back = frames.slice(1).filter((f, i) => f < frames[i]).length;
        did.hold = {
            keydowns, held_ms: HOLD_MS, latency_ms: LATENCY_MS, frames, moves: changes, back_jumps: back,
            delayed_chunks: delayed,
        };
        if (changes > 0) did.hotkeys.NEXT_FRAME = changes;
        log(`held F for ${HOLD_MS} ms (${keydowns} key-downs), each chunk request held back ${LATENCY_MS} ms `
            + `(chunks ${delayed.join(', ')}): frames shown ${JSON.stringify(frames)}`);

        // at the last frame, typed into the frame field, F moves nothing
        const field = await rectOf(page, '.cvat-player-frame-selector input');
        await keys.click(field.cx, field.cy);
        await page.evaluate('document.querySelector(".cvat-player-frame-selector input").select()');
        await page.send('Input.insertText', { text: String(job.stop_frame) });
        await keys.press('Enter');
        await page.waitFor(`Number(document.querySelector(".cvat-player-slider .ant-slider-handle")?.getAttribute("aria-valuenow")) === ${job.stop_frame}`, 'the last frame');
        await page.evaluate('document.activeElement && document.activeElement.blur()');
        await keys.move(bg.x - 150, bg.y + 20);
        await keys.press('f');
        await sleep(1500);
        const atLast = await shownFrame(page);
        did.last_frame = { frame: job.stop_frame, pressed: 1, moved: atLast !== job.stop_frame };
        log(`F at the last frame (${job.stop_frame}): frame now ${atLast}`);

        // the slider: a press near its start shows an earlier frame; no hotkey may be credited for it
        const rail = await rectOf(page, '.cvat-player-slider');
        await keys.click(rail.x + 3, rail.cy);
        await page.waitFor(`Number(document.querySelector(".cvat-player-slider .ant-slider-handle")?.getAttribute("aria-valuenow")) < ${job.stop_frame}`, 'the slider moved back', 30000);
        await sleep(1500);
        did.slider = { from: job.stop_frame, to: await shownFrame(page) };
        log(`slider pressed near its start: frame ${did.slider.from} -> ${did.slider.to}`);

        // leave the job through the header: the view writes its last input summary with the closing save
        const tasks = await rectOf(page, '.cvat-header-tasks-button');
        await keys.click(tasks.cx, tasks.cy);
        await page.waitFor('location.pathname === "/tasks"', 'the tasks page');
        await sleep(5000);
        did.event_posts = posts;
        log(`left the job; ${posts.length} POST /api/events: ${JSON.stringify(posts.map((p) => p.status))}`);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
    state.did = did;
    fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
}

// ---------------------------------------------------------------- look

// The page scrolls inside CVAT's layout, not the document, so the window is made as tall as the page for the
// shot and set back after it.
async function fullShot(page, name, width) {
    const tall = await page.evaluate(`(() => {
        const e = document.querySelector(".cvat-team-analytics-page");
        return Math.ceil(e.getBoundingClientRect().top + e.scrollHeight + 40);
    })()`);
    await page.send('Emulation.setDeviceMetricsOverride', {
        width, height: Math.min(tall, 16000), deviceScaleFactor: 1, mobile: false,
    });
    await sleep(1500);
    const { data } = await page.send('Page.captureScreenshot', { format: 'png' });
    await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, 'base64'));
}

// the split bars of the two working-time cards and the definitions block, as laid out
const LOOK = `(() => {
    const within = (r, box) => r.left >= box.left - 1 && r.right <= box.right + 1;
    const view = document.querySelector(".cvat-team-analytics-page").getBoundingClientRect();
    const cards = ["annotator", "project"].map((kind) => {
        const card = document.querySelector(".cvat-team-analytics-working-time-by-" + kind);
        if (!card) return { kind, missing: true };
        const box = card.getBoundingClientRect();
        const rows = [...card.querySelectorAll(".cvat-team-analytics-breakdown-row")].map((row) => {
            const parts = [...row.querySelectorAll(".cvat-team-analytics-bar-part")]
                .map((p) => p.getBoundingClientRect()).filter((r) => r.width > 0);
            return { parts: parts.length, inside: parts.every((r) => within(r, box)) };
        });
        const legend = [...card.querySelectorAll(".cvat-team-analytics-breakdown-legend-item")].map((e) => e.textContent.trim());
        return { kind, rows, legend, inside: within(box, view) };
    });
    const defs = document.querySelector(".cvat-team-analytics-definitions");
    const d = defs ? defs.getBoundingClientRect() : null;
    const items = defs ? [...defs.querySelectorAll(".cvat-team-analytics-definition")].map((e) => e.getBoundingClientRect()) : [];
    const details = document.querySelector(".cvat-team-analytics-details")?.getBoundingClientRect();
    const others = [...document.querySelectorAll(".cvat-team-analytics-page .cvat-team-analytics-card")]
        .map((c) => c.getBoundingClientRect().bottom);
    return {
        width: window.innerWidth,
        page: [Math.round(view.left), Math.round(view.right)],
        sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
        app: document.documentElement.scrollWidth,
        cards,
        definitions: d && {
            terms: [...defs.querySelectorAll(".cvat-team-analytics-definition-term")].map((e) => e.textContent.trim()),
            columns: new Set(items.map((r) => Math.round(r.left))).size,
            inside_page: within(d, view),
            inside_window: d.left >= -1 && d.right <= window.innerWidth + 1,
            items_inside: items.every((r) => within(r, d)),
            below_details: !!details && d.top >= details.bottom - 1,
            last: others.every((bottom) => d.top >= bottom - 1),
        },
        in_full_view: !!document.querySelector(".cvat-team-analytics-full-view .cvat-team-analytics-definitions"),
    };
})()`;

// `split`: some row of each card must be in two parts or more (an organization whose rows have several
// operations; the volume's rows are almost all creation, so there a bar in one part is right)
async function look(org, split) {
    check(!!SHOTS, 'TA_SCREENSHOT_DIR must name a directory outside the repository for the screenshots');
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-fixes-'));
    let browser;
    try {
        browser = await launch(profile);
        const owner = org === 'ta-org-c' ? 'ta-owner-c' : 'ta-owner-v'; // the volume's owner (final_run.py VOLUME_OWNER)
        const page = await signIn(browser, owner, org);
        await page.goto(`${BASE}/team-analytics?period=week&org=${org}`);
        await page.waitFor('!!document.querySelector(".cvat-team-analytics-annotator-row") && !document.querySelector(".cvat-team-analytics-pending") && !document.querySelector(".cvat-team-analytics-loading") && !!document.querySelector(".cvat-team-analytics-definitions")', 'the overview', 90000);
        // the address names no shapes: a period with shape-tagged events opens on Bounding boxes
        const pressed = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-shape[aria-pressed=\\"true\\"]")].map((e) => e.textContent.trim())');
        check(pressed.length === 1 && pressed[0] === 'Bounding boxes', `the shape switch opens on ${JSON.stringify(pressed)}`);
        log(`opened without a shapes choice: the switch reads ${pressed[0]}`);
        for (const width of [1400, 400]) {
            await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
            await sleep(2500);
            const seen = await page.evaluate(LOOK);
            await fullShot(page, `look-${org}-${width}`, width);
            for (const card of seen.cards) {
                check(!card.missing, `no ${card.kind} card at ${width} px`);
                check(card.legend.length >= 2, `${card.kind} card legend at ${width} px: ${JSON.stringify(card.legend)}`);
                check(card.rows.length > 0 && card.rows.every((r) => r.parts >= 1 && r.inside)
                    && (!split || card.rows.some((r) => r.parts >= 2)),`${card.kind} card bars at ${width} px: ${JSON.stringify(card.rows)}`);
            }
            const d = seen.definitions;
            check(!!d && d.terms.length === 4 && d.items_inside && d.inside_page && d.inside_window && d.below_details && d.last,
                `definitions at ${width} px: ${JSON.stringify(d)}`);
            if (width === 400) {
                check(d.columns === 1, `definitions at 400 px in ${d.columns} columns`);
                check(seen.page[0] >= 0 && seen.page[1] <= 400, `the page at 400 px spans ${JSON.stringify(seen.page)}`);
            } else {
                check(d.columns >= 2, `definitions at 1400 px in ${d.columns} column(s)`);
                check(!seen.sideways, `the page scrolls sideways at 1400 px (${seen.app} px)`);
            }
            log(`${width} px: bars split by operation in both cards (legends ${seen.cards.map((c) => c.legend.join('/')).join('; ')}; `
                + `${seen.cards.map((c) => `${c.rows.filter((r) => r.parts >= 2).length}/${c.rows.length} rows in several parts`).join(', ')}); `
                + `definitions ${d.terms.join(' ')} in ${d.columns} column(s), below the details table, last, inside the page's column`
                + `${width === 400 ? ` (CVAT's own header keeps the app ${seen.app} px wide)` : ''}; screenshot look-${org}-${width}.png`);
        }
        // a full view shows no definitions
        await page.send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
        await page.goto(`${BASE}/team-analytics?period=week&org=${org}&view=annotators`);
        await page.waitFor('document.querySelectorAll(".cvat-team-analytics-full-list-row").length > 0', 'the full view', 90000);
        const inFull = await page.evaluate('!!document.querySelector(".cvat-team-analytics-definitions")');
        check(!inFull, 'the full view shows the definitions');
        log('full view: no definitions');
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

const [phase, arg, option] = process.argv.slice(2);
const phases = { gestures, look };
if (!phases[phase] || !arg) {
    process.stderr.write('usage: fixes_browser.cjs gestures STATE | look ORG [split]\n');
    process.exit(2);
}
phases[phase](arg, option === 'split').catch((error) => {
    process.stderr.write(`fixes browser check (${phase}) failed: ${error.message}\n`);
    process.exit(1);
});
