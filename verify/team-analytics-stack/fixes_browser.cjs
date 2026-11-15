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
//   node fixes_browser.cjs look ORG [split] the overview of ORG (read by ta-admin, the only readers being
//                                           administrators) at 1400 px and at 400 px: the split bars of the
//                                           two working-time cards (with split, some row of each in several
//                                           parts), no definitions block (the definitions are tooltips on the
//                                           terms: page ORG checks them), judged from the page's layout;
//                                           full-page screenshots for the comparison with the prototype,
//                                           which a person makes.
//   node fixes_browser.cjs page ORG         the page after tickets 02-06, as ta-admin in ORG: the filter bar
//                                           and the Settings button at one height (1024, 1400, 1920 px), the
//                                           operations card without sideways scroll over a width sweep, the
//                                           project and annotator selectors (an open popup never makes the page
//                                           scroll sideways and stays inside the page container), the terms'
//                                           tooltips, the settings modal (an account already on the list is
//                                           offered disabled, marked "already on the list") saving the same
//                                           list, and nothing left of what they replaced.
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
// the volume's organization (final_run.py load-volume, part of check-final): several projects and annotators
const VOLUME_ORG = process.env.TA_VOLUME_ORG || 'ta-org-v';
const SHOTS = process.env.TA_SCREENSHOT_DIR || '';
const LATENCY_MS = 1500; // each request for frame data is held back this long while F is held
const HOLD_MS = 4000;
const REPEAT_MS = 50; // a held key's auto-repeat

// ---------------------------------------------------------------- input

const KEYS = {
    Control: { code: 'ControlLeft', keyCode: 17 },
    Shift: { code: 'ShiftLeft', keyCode: 16 },
    Enter: { code: 'Enter', keyCode: 13, text: '\r' },
    Escape: { code: 'Escape', keyCode: 27 },
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

// the split bars of the two working-time cards, as laid out, and whether anything of the old definitions block is left
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
    return {
        width: window.innerWidth,
        page: [Math.round(view.left), Math.round(view.right)],
        sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
        app: document.documentElement.scrollWidth,
        cards,
        definitions: document.querySelectorAll(".cvat-team-analytics-definitions, .cvat-team-analytics-definition").length,
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
        // only administrators read Team Analytics: ta-admin with the organization selected
        const page = await signIn(browser, 'ta-admin', org);
        await page.goto(`${BASE}/team-analytics?period=week&org=${org}`);
        await overviewReady(page, 'the overview');
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
            check(seen.definitions === 0, `the old definitions block is still on the page at ${width} px (${seen.definitions} elements)`);
            if (width === 400) {
                check(seen.page[0] >= 0 && seen.page[1] <= 400, `the page at 400 px spans ${JSON.stringify(seen.page)}`);
            } else {
                check(!seen.sideways, `the page scrolls sideways at 1400 px (${seen.app} px)`);
            }
            log(`${width} px: bars split by operation in both cards (legends ${seen.cards.map((c) => c.legend.join('/')).join('; ')}; `
                + `${seen.cards.map((c) => `${c.rows.filter((r) => r.parts >= 2).length}/${c.rows.length} rows in several parts`).join(', ')}); `
                + `no definitions block${width === 400 ? ` (CVAT's own header keeps the app ${seen.app} px wide)` : ''}; screenshot look-${org}-${width}.png`);
        }
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

// ---------------------------------------------------------------- the page after tickets 02-06

async function overviewReady(page, what) {
    await page.waitFor('!!document.querySelector(".cvat-team-analytics-annotator-row") && !document.querySelector(".cvat-team-analytics-pending") && !document.querySelector(".cvat-team-analytics-loading")', what, 90000);
    await sleep(1500);
}

// The page in `org` (a slug; "" for instance scope, no organization). The page reads its organization from the one
// CVAT has selected, not from the address: an `org=` in the address alone is replaced by the selected one. So CVAT's
// selection (localStorage "currentOrganization", read when the app loads, as browser_check.cjs signIn sets it) is
// switched first, then the page is loaded, and both the header and the address must name `org` before anything
// is measured.
async function openTA(page, org, query) {
    await page.evaluate(org ? `localStorage.setItem("currentOrganization", ${JSON.stringify(org)})`
        : 'localStorage.removeItem("currentOrganization")');
    await page.goto(`${BASE}/team-analytics?${query}${org ? `&org=${org}` : ''}`);
    if (org) {
        await page.waitFor(`document.querySelector(".cvat-header-menu-user-dropdown-organization")?.textContent.trim() === ${JSON.stringify(org)}`,
            `CVAT's selected organization ${org} in the header`, 30000);
    }
    const inAddress = await page.waitFor(`(() => { const o = new URLSearchParams(location.search).get("org") || "";
        return o === ${JSON.stringify(org)} ? (o || "(none)") : null; })()`, `org=${org || '(none)'} in the address`, 30000)
        .catch(async () => `${await page.evaluate('location.search')} (expected org=${org || 'none'})`);
    check(inAddress === (org || '(none)'), `the page did not open in ${org || 'instance scope'}: the address reads ${inAddress}`);
    log(`[${org || 'instance scope'}] /team-analytics?${query}: CVAT's selected organization and the address name ${org || 'no organization'}`);
}

const setWidth = (page, width, height = 900) => page.send('Emulation.setDeviceMetricsOverride', {
    width, height, deviceScaleFactor: 1, mobile: false,
});

// the glossary's wording, as the terms' tooltips carry it (cvat-ui/src/components/team-analytics-page/definitions.tsx)
const TERM_TEXTS = {
    Session: 'One uninterrupted interval of job work by one person, at most a day long. A pause longer than five minutes ends it. Seen for a single project, a session counts if it touched that project, and its length is only the time spent inside it.',
    'Working time': 'The time the server counts as worked, the same figure Grafana reports. It is the only total: every breakdown of time adds up to it.',
    'Time per operation': 'The time from a person\'s previous action to the end of the operation, so that finding, deciding and pointing are part of it. A pause longer than 100 seconds before an action belongs to no operation.',
    Model: 'Created without a person drawing it: saved by a technical account or produced by the built-in detector. Model boxes have counts but no time.',
};
const termOf = (label) => {
    const l = label.toLowerCase();
    if (l === 'sessions') return 'Session';
    if (l === 'working time') return 'Working time';
    if (l === 'model') return 'Model';
    if (l.startsWith('avg time')) return 'Time per operation';
    return null;
};

const CONTROLS = ['.cvat-team-analytics-periods', '.cvat-team-analytics-shapes', '.cvat-team-analytics-step',
    '.cvat-team-analytics-filter-project', '.cvat-team-analytics-filter-annotator'];
const BAR = `(() => {
    const box = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
        return { height: Math.round(b.height * 10) / 10, centre: Math.round((b.top + b.height / 2) * 10) / 10 }; };
    const header = document.querySelector(".cvat-team-analytics-header")?.getBoundingClientRect();
    const button = document.querySelector(".cvat-team-analytics-header .cvat-team-analytics-settings-button");
    const b = button?.getBoundingClientRect();
    const chips = document.querySelector(".cvat-team-analytics-filter-chips");
    return {
        controls: Object.fromEntries(${JSON.stringify(CONTROLS)}.map((s) => [s, box(s)])),
        freshness: box(".cvat-team-analytics-freshness"),
        settings: b ? { height: Math.round(b.height * 10) / 10, right: Math.round(b.right), header_right: Math.round(header.right),
            gear: !!button.querySelector(".anticon-setting"), text: button.textContent.trim() } : null,
        chips_margin: chips ? getComputedStyle(chips).marginBottom : null,
    };
})()`;

// 1. every filter control and the Settings button 36 px tall; controls on one line share a centre (±0.5 px)
async function filterBar(page, org) {
    const month = new Date().toISOString().slice(0, 7); // a month period shows the step arrows too
    await openTA(page, org, `period=month&month=${month}`);
    await overviewReady(page, `the month ${month}`);
    for (const width of [1024, 1400, 1920]) {
        await setWidth(page, width);
        await sleep(1500);
        const bar = await page.evaluate(BAR);
        const missing = CONTROLS.filter((s) => !bar.controls[s]);
        check(!missing.length, `${width} px: no ${missing.join(', ')} on the month's filter bar`);
        const heights = Object.entries(bar.controls).filter(([, c]) => Math.abs(c.height - 36) > 0.5);
        check(!heights.length, `${width} px: controls not 36 px tall: ${JSON.stringify(heights)}`);
        // controls whose centres lie within 20 px are on one line (a wrapped line is 36 px and a gap further down)
        const lines = [];
        for (const [s, c] of Object.entries(bar.controls)) {
            const line = lines.find((l) => Math.abs(l.centre - c.centre) < 20);
            if (line) line.items.push([s, c.centre]); else lines.push({ centre: c.centre, items: [[s, c.centre]] });
        }
        const off = lines.filter((l) => Math.max(...l.items.map((i) => i[1])) - Math.min(...l.items.map((i) => i[1])) > 0.5);
        check(!off.length, `${width} px: controls on one line with different centres: ${JSON.stringify(off)}`);
        if (width === 1920) check(lines.length === 1, `1920 px: the filter bar wraps into ${lines.length} lines: ${JSON.stringify(lines)}`);
        check(!bar.freshness || bar.freshness.height >= 35.5, `${width} px: freshness ${JSON.stringify(bar.freshness)}, expected at least 36 px`);
        const st = bar.settings;
        check(!!st && Math.abs(st.height - 36) <= 0.5 && Math.abs(st.right - st.header_right) <= 1 && st.gear && st.text === 'Settings',
            `${width} px: the Settings button ${JSON.stringify(st)}, expected "Settings" with a gear, 36 px, at the header's right end`);
        check(bar.chips_margin === '0px', `${width} px: the filter chips' margin-bottom is ${bar.chips_margin}, expected 0px`);
        log(`${width} px: ${CONTROLS.length} controls 36 px on ${lines.length} line(s) (centres ${lines.map((l) => l.centre).join(', ')}); `
            + `Settings 36 px at the header's right end; freshness ${bar.freshness ? `${bar.freshness.height} px` : 'not shown'}`);
    }
}

// 2. the operations card never scrolls sideways from 1024 to 1920 px: every 8 px, and every width at which the cards'
// grid (repeat(auto-fit, minmax(min(100%, 420px), 1fr)), 16 px gap) changes its number of columns, which is where a
// card is narrowest (420 px when the content box allows it). The change widths are found on the page itself: between
// two sweep widths with different column counts, every pixel is measured. Other tables that scroll sideways are
// listed with their card and widths, not judged.
const SWEEP = `(() => {
    const card = document.querySelector("section.cvat-team-analytics-operations");
    const wrap = card?.querySelector(".cvat-team-analytics-operations-scroll");
    const grid = card?.closest(".cvat-team-analytics-cards");
    const columns = grid ? getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length : 0;
    const others = [...document.querySelectorAll(".cvat-team-analytics-page .cvat-team-analytics-table-scroll")]
        .filter((t) => t !== wrap && t.scrollWidth > t.clientWidth + 1)
        .map((t) => (t.closest("section")?.className || "?").split(" ").filter((c) => c !== "cvat-team-analytics-card").join("."));
    return { card: card ? Math.round(card.getBoundingClientRect().width * 10) / 10 : null, columns,
        scroll: wrap ? [wrap.scrollWidth, wrap.clientWidth] : null, others };
})()`;

async function widthSweep(page, org) {
    await setWidth(page, 1400);
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    const seen = new Map();
    const scrolling = new Map();
    const measure = async (width) => {
        if (seen.has(width)) return seen.get(width);
        await setWidth(page, width);
        await sleep(200);
        const m = await page.evaluate(SWEEP);
        seen.set(width, m);
        m.others.forEach((name) => scrolling.set(name, [...(scrolling.get(name) || []), width]));
        return m;
    };
    const coarse = [];
    for (let width = 1024; width <= 1920; width += 8) coarse.push(width);
    if (coarse[coarse.length - 1] !== 1920) coarse.push(1920);
    for (const width of coarse) await measure(width);
    const changes = [];
    for (let i = 1; i < coarse.length; i++) {
        if (seen.get(coarse[i]).columns === seen.get(coarse[i - 1]).columns) continue;
        for (let width = coarse[i - 1] + 1; width < coarse[i]; width++) await measure(width);
        for (let width = coarse[i - 1] + 1; width <= coarse[i]; width++) {
            if (seen.get(width).columns !== seen.get(width - 1).columns) {
                changes.push(`${width} px: ${seen.get(width - 1).columns} -> ${seen.get(width).columns} columns, card ${seen.get(width).card} px`);
            }
        }
    }
    const measured = [...seen.entries()].filter(([, m]) => m.card !== null);
    const [narrowW, narrowM] = measured.sort((a, b) => a[1].card - b[1].card)[0];
    const wrong = [...seen.entries()].filter(([, m]) => !m.scroll || m.scroll[0] > m.scroll[1]).map(([w, m]) => [w, m.scroll]);
    log(`width sweep: ${seen.size} widths from 1024 to 1920 px (every 8 px, every pixel around a change of columns); `
        + `column changes: ${changes.join('; ') || 'none'}; narrowest operations card ${narrowM.card} px at ${narrowW} px`);
    log(`other cards whose table scrolls sideways (card: widths): ${scrolling.size ? [...scrolling.entries()].map(([n, ws]) => `${n}: ${ws.length} widths, ${Math.min(...ws)}-${Math.max(...ws)} px`).join('; ') : 'none'}`);
    check(!wrong.length, `expected scrollWidth <= clientWidth on the operations wrapper at every width; it scrolls sideways at `
        + `${JSON.stringify(wrong.slice(0, 10))} (width, [scrollWidth, clientWidth])`);
    await setWidth(page, 1400);
}

// the operations card's table: five columns, four operations each with its split row under it
const OPERATIONS = `(() => {
    const card = document.querySelector("section.cvat-team-analytics-operations");
    const table = card?.querySelector("table.cvat-team-analytics-operations-table");
    if (!table) return null;
    const groups = [...table.querySelectorAll("tbody.cvat-team-analytics-operation-group")].map((g) => {
        const th = g.querySelector("tr.cvat-team-analytics-operation-row th[scope=row]");
        const split = g.querySelector("tr.cvat-team-analytics-input-split-row td.cvat-team-analytics-input-split");
        return { name: th?.querySelector(".cvat-team-analytics-operation-name")?.textContent.trim(),
            cells: g.querySelectorAll("tr.cvat-team-analytics-operation-row td").length,
            split: split && { colspan: split.getAttribute("colspan"), headers_ok: !!th?.id && split.getAttribute("headers") === th.id,
                text: split.textContent.trim() } };
    });
    return { columns: [...table.querySelectorAll("thead th[scope=col]")].map((th) => th.textContent.trim()),
        old_table: table.classList.contains("cvat-team-analytics-table") || !!card.querySelector("table.cvat-team-analytics-table"),
        started_by: card.textContent.includes("Started by hotkey"), groups };
})()`;

async function operationsTable(page) {
    const t = await page.evaluate(OPERATIONS);
    check(!!t, 'no table.cvat-team-analytics-operations-table in the operations card');
    log(`operations table: columns ${JSON.stringify(t.columns)}; ${t.groups.map((g) => `${g.name} (${g.split?.text})`).join(', ')}`);
    check(t.columns.length === 5 && t.columns[0] === 'Operation' && ['Boxes', 'Objects'].includes(t.columns[1])
        && t.columns[2].startsWith('Avg time') && t.columns[3] === 'Total time' && t.columns[4] === 'Share',
    `operations columns ${JSON.stringify(t.columns)}, expected Operation, Boxes or Objects, Avg time, Total time, Share`);
    check(JSON.stringify(t.groups.map((g) => g.name)) === JSON.stringify(['Creation', 'Alignment', 'Class change', 'Deletion']),
        `operation rows ${JSON.stringify(t.groups.map((g) => g.name))}`);
    check(t.groups.every((g) => g.cells === 4 && g.split && g.split.colspan === '5' && g.split.headers_ok),
        `each operation: 4 cells and a split row of colspan 5 pointing at its header: ${JSON.stringify(t.groups)}`);
    // the split cell: its hidden prefix "<Operation> started by: ", then "N% hotkey / M% mouse", or Mouse only (always
    // for Alignment), Not recorded (a legacy period) or a dash (no recorded starts)
    const splitText = /started by: (\d+% hotkey \/ \d+% mouse|Mouse only|Not recorded|—)$/;
    const odd = t.groups.filter((g) => !splitText.test(g.split.text) || (g.name === 'Alignment' && !g.split.text.endsWith('Mouse only')));
    check(!odd.length, `split rows ${JSON.stringify(odd.map((g) => [g.name, g.split.text]))}, expected "<Operation> started by: `
        + 'N% hotkey / M% mouse", "Mouse only" (always for Alignment), "Not recorded" or "—"');
    check(!t.old_table && !t.started_by, 'the operations card still has the old table class or a "Started by hotkey / mouse" header');
}

// 3. the selectors: options load, a search narrows them, a pick sets the address and changes the figures, All clears
const FIGURES = `[...document.querySelectorAll(".cvat-team-analytics-headline-value, section.cvat-team-analytics-operations tr.cvat-team-analytics-operation-row")].map((e) => e.textContent.trim()).join(" | ")`;

async function openSelector(page, keys, kind) {
    await clickSelectorIn(page, keys, `.cvat-team-analytics-filter-${kind} .cvat-team-analytics-filter-button`);
    await page.waitFor(`(() => { const p = document.querySelector(".cvat-team-analytics-filter-popup"); const s = p?.querySelector(".cvat-team-analytics-filter-status");
        return !!p && (!s || getComputedStyle(s).display === "none" || !s.textContent.includes("Loading")); })()`, `the ${kind} selector's options`, 60000);
    return page.evaluate(`(() => {
        const button = document.querySelector(".cvat-team-analytics-filter-${kind} .cvat-team-analytics-filter-button");
        const popup = document.querySelector(".cvat-team-analytics-filter-popup");
        const r = popup.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        // not clipped: inside the window, and no ancestor that clips it is narrower or shorter than it
        let clippedBy = null;
        for (let e = popup.parentElement; e && e !== document.body; e = e.parentElement) {
            const s = getComputedStyle(e);
            if (["hidden", "clip", "auto", "scroll"].some((v) => s.overflowX === v || s.overflowY === v)) {
                const b = e.getBoundingClientRect();
                if (r.left < b.left - 1 || r.right > b.right + 1 || r.top < b.top - 1 || r.bottom > b.bottom + 1) { clippedBy = e.className || e.tagName; break; }
            }
        }
        return { options: [...popup.querySelectorAll("li.cvat-team-analytics-filter-option[role=option]")].map((o) => o.textContent.trim()),
            expanded: button.getAttribute("aria-expanded"), focused: document.activeElement?.classList.contains("cvat-team-analytics-filter-search"),
            on_top: !!hit && popup.contains(hit), inside_window: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
            clipped_by: clippedBy, status: popup.querySelector(".cvat-team-analytics-filter-status")?.textContent.trim() || "" };
    })()`);
}

// the Team Analytics requests the page sends, as the browser saw them (Network.requestWillBeSent of the page)
function watchApi(browser, page) {
    const seen = [];
    browser.listeners.add((message) => {
        if (message.sessionId !== page.sessionId || message.method !== 'Network.requestWillBeSent') return;
        const { request } = message.params;
        const url = new URL(request.url);
        if (url.pathname.startsWith('/api/team-analytics/')) seen.push({ method: request.method, path: url.pathname, query: url.searchParams });
    });
    return seen;
}

const popupOpen = (page) => page.evaluate('!!document.querySelector(".cvat-team-analytics-filter-popup")');

// opening sends exactly one list request with `by` and no project, annotator or shapes; opening again sends none;
// Escape and a mousedown outside close it
async function selectorRequests(page, keys, api, kind) {
    const by = kind === 'project' ? 'projects' : 'annotators';
    const from = api.length;
    await openSelector(page, keys, kind);
    await sleep(500);
    const lists = api.slice(from).filter((r) => r.path.endsWith('/list'));
    const q = lists[0]?.query;
    const describe = lists.map((r) => `${r.method} ${r.path}?${r.query.toString()}`);
    check(lists.length === 1 && q.get('by') === by && !['project', 'annotator', 'shapes'].some((k) => q.has(k)),
        `opening the ${kind} selector sent ${JSON.stringify(describe)}, expected exactly one GET list with by=${by} and no project, annotator or shapes`);
    await keys.press('Escape');
    const afterEscape = await popupOpen(page);
    const focusBack = await page.evaluate(`document.activeElement?.classList.contains("cvat-team-analytics-filter-button") && !!document.activeElement.closest(".cvat-team-analytics-filter-${kind}")`);
    check(!afterEscape && focusBack, `Escape: popup still open ${afterEscape}, focus back on the ${kind} button ${focusBack}`);
    const again = api.length;
    await openSelector(page, keys, kind);
    await sleep(500);
    const repeated = api.slice(again).filter((r) => r.path.endsWith('/list'));
    check(repeated.length === 0, `opening the ${kind} selector again sent ${repeated.length} more list requests, expected none`);
    await keys.click(5, 300); // a mousedown on the page's left edge, outside the popup
    check(!(await popupOpen(page)), `a click outside left the ${kind} selector open`);
    log(`${kind} selector: one request ${describe[0]}; none on reopening; Escape closes and returns focus; a click outside closes`);
}

async function clickSelectorIn(page, keys, selector, index = 0) {
    await page.waitFor(`document.querySelectorAll(${JSON.stringify(selector)}).length > ${index}`, selector);
    await page.evaluate(`document.querySelectorAll(${JSON.stringify(selector)})[${index}].scrollIntoView({block: "center"})`);
    await sleep(300);
    const r = await page.evaluate(`(() => { const b = document.querySelectorAll(${JSON.stringify(selector)})[${index}].getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; })()`);
    await keys.click(r.x, r.y);
}

async function pick(page, keys, kind) {
    const before = await page.evaluate(FIGURES);
    const opened = await openSelector(page, keys, kind);
    const all = kind === 'project' ? 'All projects' : 'All annotators';
    check(opened.expanded === 'true' && opened.focused && opened.on_top && opened.inside_window && !opened.clipped_by,
        `the ${kind} selector opened: aria-expanded ${opened.expanded}, search focused ${opened.focused}, drawn over the cards `
        + `${opened.on_top}, inside the window ${opened.inside_window}, clipped by ${opened.clipped_by}; expected true, true, true, true, none`);
    check(opened.options[0] === all && opened.options.length >= 3,
        `${kind} options ${JSON.stringify(opened.options)} (status "${opened.status}"), expected "${all}" first and at least two to pick from`);
    // a named one: "No project" names no project to search for
    const target = opened.options.slice(1).find((o) => o !== 'No project');
    check(!!target, `no ${kind} with a name among ${JSON.stringify(opened.options)}`);
    await page.send('Input.insertText', { text: target });
    await sleep(800);
    const narrowed = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-filter-popup li.cvat-team-analytics-filter-option")].map((o) => o.textContent.trim())');
    check(narrowed[0] === all && narrowed.length < opened.options.length && narrowed.slice(1).every((o) => o.toLowerCase().includes(target.toLowerCase())),
        `a search for "${target}" left ${JSON.stringify(narrowed)} of ${opened.options.length} options`);
    check(narrowed.includes(target), `the search for "${target}" lost the option itself: ${JSON.stringify(narrowed)}`);
    await clickSelectorIn(page, keys, '.cvat-team-analytics-filter-popup li.cvat-team-analytics-filter-option', narrowed.indexOf(target));
    await page.waitFor(`location.search.includes("${kind}=") && !document.querySelector(".cvat-team-analytics-filter-popup")`, `${kind}= in the address`);
    await overviewReady(page, `the ${kind} filter`);
    const shown = await page.evaluate(`document.querySelector(".cvat-team-analytics-filter-${kind} .cvat-team-analytics-filter-button").textContent.trim()`);
    const after = await page.evaluate(FIGURES);
    check(shown.includes(target), `the ${kind} button reads "${shown}", expected the picked "${target}"`);
    check(after !== before, `the figures did not change with ${kind} "${target}": ${after}`);
    log(`${kind}: ${opened.options.length} options, "${target}" narrows them to ${narrowed.length}; picked: ${await page.evaluate('location.search')}; `
        + `figures ${before.slice(0, 80)} -> ${after.slice(0, 80)}`);
    return before;
}

async function selectors(page, keys, api, org) {
    await setWidth(page, 1400);
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    await selectorRequests(page, keys, api, 'project');
    await selectorRequests(page, keys, api, 'annotator');
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    const unfiltered = await pick(page, keys, 'project');
    await pick(page, keys, 'annotator');
    // All in the project selector, then the annotator's clear button
    await openSelector(page, keys, 'project');
    await clickSelectorIn(page, keys, '.cvat-team-analytics-filter-popup .cvat-team-analytics-filter-option-all');
    await page.waitFor('!location.search.includes("project=")', 'project= gone after All');
    await clickSelectorIn(page, keys, '.cvat-team-analytics-filter-annotator .cvat-team-analytics-filter-clear');
    await page.waitFor('!location.search.includes("annotator=")', 'annotator= gone after the clear button');
    await overviewReady(page, 'no filter');
    const cleared = await page.evaluate(FIGURES);
    check(cleared === unfiltered, `after All and the clear button the figures are ${cleared}, before any filter ${unfiltered}`);
    log('All and the clear button removed both filters; the figures are as before');
}

// 3b. an open selector never makes the page scroll sideways: at 1024 and 1400 px and at the width of the sweep where
// the Annotator selector's right edge comes nearest the container's right edge, the scroll widths of the document
// and of the page container (.cvat-team-analytics-page, which scrolls) are taken with every selector closed; with
// each popup open neither is wider than that, the page container has scrollWidth <= clientWidth (CVAT's own layout
// may make the document wider than a 1024 px window by itself: that is recorded, not judged), and the popup's box
// and its longest option lie inside the container (its left edge to its left edge plus its client width)
const POPUP_FIT = `(() => {
    const popup = document.querySelector(".cvat-team-analytics-filter-popup");
    const page = document.querySelector(".cvat-team-analytics-page");
    if (!popup || !page) return null;
    const r = popup.getBoundingClientRect();
    const p = page.getBoundingClientRect();
    const right = p.left + (page.clientWidth || p.width);
    const s = document.scrollingElement;
    const longest = popup.querySelector("li.cvat-team-analytics-filter-option.cvat-ta-longest-option");
    const l = longest?.getBoundingClientRect();
    return { document: [s.scrollWidth, s.clientWidth], page: [page.scrollWidth, page.clientWidth],
        popup: [Math.round(r.left * 10) / 10, Math.round(r.right * 10) / 10], container: [Math.round(p.left * 10) / 10, Math.round(right * 10) / 10],
        inside: r.left >= p.left - 0.5 && r.right <= right + 0.5,
        longest: longest ? { text: longest.textContent.trim(), box: [Math.round(l.left), Math.round(l.right)] } : null,
        longest_inside: !!longest && l.left >= p.left - 0.5 && l.right <= right + 0.5,
        side: [...popup.classList].find((c) => c.startsWith("cvat-team-analytics-filter-popup-")) || "" };
})()`;
// [scrollWidth, clientWidth] of the document and of the page container
const SCROLL_WIDTHS = `(() => { const s = document.scrollingElement; const p = document.querySelector(".cvat-team-analytics-page");
    return { document: [s.scrollWidth, s.clientWidth], page: p ? [p.scrollWidth, p.clientWidth] : [0, 0] }; })()`;
// the element whose box reaches furthest right beyond the window, the innermost of those that reach as far (the
// last in document order), for the record only
const WIDEST_BEYOND = `(() => {
    let best = null;
    for (const e of document.body.querySelectorAll("*")) {
        const r = e.getBoundingClientRect();
        if (r.right > innerWidth + 0.5 && (!best || r.right >= best.right)) {
            best = { tag: e.tagName.toLowerCase(), class: String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className).slice(0, 160),
                right: Math.round(r.right), width: Math.round(r.width), parent: String(e.parentElement?.className || "").slice(0, 120) };
        }
    }
    return best;
})()`;
// the options are in: the status line is gone, empty or hidden, and a named option (not "All ...") is listed
const OPTIONS_LOADED = `(() => {
    const popup = document.querySelector(".cvat-team-analytics-filter-popup");
    if (!popup) return false;
    const s = popup.querySelector(".cvat-team-analytics-filter-status");
    const quiet = !s || getComputedStyle(s).display === "none" || !s.checkVisibility() || s.textContent.trim() === "";
    return quiet && popup.querySelectorAll("li.cvat-team-analytics-filter-option[role=option]:not(.cvat-team-analytics-filter-option-all)").length > 0;
})()`;
// the option with the longest name is scrolled into view and marked (a class of this check only) for POPUP_FIT
const SHOW_LONGEST = `(() => {
    const options = [...document.querySelectorAll(".cvat-team-analytics-filter-popup li.cvat-team-analytics-filter-option[role=option]")];
    const longest = options.reduce((a, b) => (b.scrollWidth > a.scrollWidth || (b.scrollWidth === a.scrollWidth && b.textContent.length > a.textContent.length) ? b : a));
    longest.classList.add("cvat-ta-longest-option");
    longest.scrollIntoView({ block: "nearest" });
})()`;
const ANNOTATOR_GAP = `(() => {
    const box = document.querySelector(".cvat-team-analytics-filter-annotator")?.getBoundingClientRect();
    const page = document.querySelector(".cvat-team-analytics-page");
    if (!box || !page) return null;
    return Math.round((page.getBoundingClientRect().left + page.clientWidth - box.right) * 10) / 10;
})()`;

async function popupFit(page, keys, org) {
    await setWidth(page, 1400);
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    // the width at which the Annotator selector sits nearest the container's right edge
    let edge = null;
    for (let width = 1024; width <= 1920; width += 8) {
        await setWidth(page, width);
        await sleep(150);
        const gap = await page.evaluate(ANNOTATOR_GAP);
        if (gap !== null && (!edge || gap < edge.gap)) edge = { width, gap };
    }
    check(!!edge, 'no Annotator selector found on the filter bar between 1024 and 1920 px');
    log(`the Annotator selector is nearest the page container's right edge at ${edge.width} px (${edge.gap} px from it)`);
    const wrong = [];
    let widest = null;
    for (const width of [1024, 1400, edge.width]) {
        await setWidth(page, width);
        await sleep(800);
        // the baseline: CVAT's own layout may be wider than the window at its narrowest (the document scrolls then
        // with no popup open); a popup must not add to that
        const closed = await page.evaluate(SCROLL_WIDTHS);
        log(`${width} px, selectors closed: document ${closed.document.join('/')}, page ${closed.page.join('/')}`);
        if (closed.document[0] > closed.document[1] && !widest) {
            widest = await page.evaluate(WIDEST_BEYOND);
            log(`for the record, not judged: at ${width} px with the selectors closed the document is wider than the window; `
                + `the element reaching furthest right: ${JSON.stringify(widest)}`);
        }
        if (closed.page[0] > closed.page[1]) wrong.push([width, 'selectors closed', closed]);
        for (const kind of ['project', 'annotator']) {
            await openSelector(page, keys, kind);
            // measured once the names are in: while "Loading…" shows the popup is at its narrowest
            await page.waitFor(OPTIONS_LOADED, `the ${kind} selector's options loaded (status line empty or hidden, a named option)`, 60000);
            await page.evaluate(SHOW_LONGEST);
            await sleep(300);
            const fit = await page.evaluate(POPUP_FIT);
            log(`${width} px, ${kind} selector open: ${JSON.stringify(fit)}`);
            // with the popup open: neither the document nor the page container wider than with it closed, the page
            // container (the fork's own element) never scrolling sideways, the popup and its longest option inside it
            if (!fit || fit.document[0] > closed.document[0] || fit.page[0] > closed.page[0] || fit.page[0] > fit.page[1]
                || !fit.inside || !fit.longest_inside) {
                wrong.push([width, kind, { closed, open: fit }]);
            }
            await keys.press('Escape');
            await page.waitFor('!document.querySelector(".cvat-team-analytics-filter-popup")', 'the popup closed by Escape', 5000);
        }
    }
    check(!wrong.length, `an open selector widened the document or the page container, the page container scrolls sideways, `
        + `or the popup passed the page container: ${JSON.stringify(wrong)} (width, selector, {closed: document and page `
        + '[scrollWidth, clientWidth] with the selectors closed, open: the same with the popup open, popup [left, right], '
        + 'container [left, right]}); expected no scroll width above the closed one, page scrollWidth <= clientWidth, and '
        + 'the popup and its longest option inside the container');
    await setWidth(page, 1400);
}

// 4. every term's tooltip: shown on hover and on keyboard focus, inside the window, with the glossary's text.
// Where the 13 terms of the overview sit, in document order: the section (class) around each, and its term
const PLACES = [
    ['cvat-team-analytics-sessions', 'Session'],
    ['cvat-team-analytics-average-creation', 'Time per operation'],
    ['cvat-team-analytics-time-chart', 'Working time'],
    ['cvat-team-analytics-split', 'Working time'],
    ['cvat-team-analytics-operations', 'Time per operation'],
    ['cvat-team-analytics-creation-methods', 'Time per operation'],
    ['cvat-team-analytics-model-row', 'Model'],
    ['cvat-team-analytics-working-time-by-project', 'Working time'],
    ['cvat-team-analytics-working-time-by-annotator', 'Working time'],
    ['cvat-team-analytics-details', 'Session'],
    ['cvat-team-analytics-details', 'Working time'],
    ['cvat-team-analytics-details', 'Model'],
    ['cvat-team-analytics-details', 'Time per operation'],
];
const TERMS ='[...document.querySelectorAll(".cvat-team-analytics-page button.cvat-team-analytics-term")]';

async function terms(page, keys, org) {
    await setWidth(page, 1400);
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    // two terms exist only with their data: the Model row of the creation methods when the period has Model objects,
    // and the details' Model column unless the period is legacy (its column is "Boxes saved" then, with no term)
    const gates = await page.evaluate(`({ model: !!document.querySelector(".cvat-team-analytics-model-row"),
        legacy: [...document.querySelectorAll(".cvat-team-analytics-details th")].some((th) => th.textContent.trim() === "Boxes saved") })`);
    const places = PLACES.filter(([section, term]) => (section !== 'cvat-team-analytics-model-row' || gates.model)
        && !(section === 'cvat-team-analytics-details' && term === 'Model' && gates.legacy));
    log(`terms expected: ${places.length} (Model row ${gates.model ? 'shown' : 'not shown: no Model objects'}, details `
        + `${gates.legacy ? 'legacy' : 'with its Model column'})`);
    const found = await page.evaluate(`${TERMS}.map((t, i) => ({ label: t.textContent.trim(), id: t.getAttribute("aria-describedby"),
        placed: !!${JSON.stringify(places)}[i] && !!t.closest("." + ${JSON.stringify(places)}[i][0]),
        section: (t.closest("section")?.className || "").split(" ").find((c) => c !== "cvat-team-analytics-card") || "",
        titled: (() => { let e = t; const card = t.closest(".cvat-team-analytics-card"); while (e && e !== card?.parentElement) { if (e.hasAttribute("title")) return true; e = e.parentElement; } return false; })() }))`);
    log(`terms on the overview: ${found.map((f) => `${f.label} (${f.section})`).join(', ')}`);
    check(found.length === places.length, `${found.length} terms on the overview, expected ${places.length}`);
    const misplaced = found.map((f, i) => [i + 1, f.label, f.section, places[i]]).filter(([i, label]) => !found[i - 1].placed
        || termOf(label) !== places[i - 1][1]);
    check(!misplaced.length, `terms out of place (n, label, section seen, [section, term] expected): ${JSON.stringify(misplaced)}`);
    check(found.every((f) => termOf(f.label) && f.id), `terms without a known name or a tooltip id: ${JSON.stringify(found.filter((f) => !termOf(f.label) || !f.id))}`);
    check(!found.some((f) => f.titled), `terms with a native title on them or around them in their card: ${JSON.stringify(found.filter((f) => f.titled))}`);
    const tooltip = (id) => `(() => { const inner = document.getElementById(${JSON.stringify(id)}); const wrap = inner?.closest(".ant-tooltip");
        if (!inner || !wrap || wrap.classList.contains("ant-tooltip-hidden") || getComputedStyle(wrap).display === "none" || !inner.checkVisibility()) return null;
        const r = inner.getBoundingClientRect();
        return { text: inner.textContent.trim(), inside: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
            rect: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)], under_body: !inner.closest(".cvat-team-analytics-page"),
            shown: [...document.querySelectorAll(".ant-tooltip")].filter((t) => !t.classList.contains("ant-tooltip-hidden")
                && getComputedStyle(t).display !== "none" && t.checkVisibility()).length }; })()`;
    for (const [i, f] of found.entries()) {
        const want = TERM_TEXTS[termOf(f.label)];
        await page.evaluate(`${TERMS}[${i}].scrollIntoView({block: "center"})`);
        await sleep(300);
        const r = await page.evaluate(`(() => { const b = ${TERMS}[${i}].getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; })()`);
        await keys.move(r.x, r.y);
        const hovered = await page.waitFor(tooltip(f.id), `the tooltip of "${f.label}" (${f.section}) on hover`, 5000);
        await keys.move(5, 5);
        await page.waitFor(`!${tooltip(f.id)}`, `the tooltip of "${f.label}" hidden after the mouse left`, 5000);
        await page.evaluate(`${TERMS}[${i}].focus()`);
        const focused = await page.waitFor(tooltip(f.id), `the tooltip of "${f.label}" (${f.section}) on keyboard focus`, 5000);
        await page.evaluate(`${TERMS}[${i}].blur()`);
        await page.waitFor(`!${tooltip(f.id)}`, `the tooltip of "${f.label}" hidden after the focus left`, 5000);
        for (const [how, shown] of [['hover', hovered], ['focus', focused]]) {
            check(shown.text === want && shown.inside && shown.under_body && shown.shown === 1,
                `"${f.label}" (${f.section}) on ${how}: ${JSON.stringify(shown)}, expected the ${termOf(f.label)} text inside the window, `
                + 'under the body, and one tooltip shown');
        }
    }
    log(`${found.length} terms: each tooltip shown on hover and on focus, inside the window, with the glossary's text, hidden after`);
    await openTA(page, org, `period=week&view=annotators`);
    await page.waitFor('document.querySelectorAll(".cvat-team-analytics-full-list-row").length > 0', 'the full view', 90000);
    const inFull = await page.evaluate(`${TERMS}.length`);
    check(inFull === 0, `the full view has ${inFull} terms, expected none`);
    log('full view of annotators: no terms');
}

// 5. nothing left of what tickets 01-04 replaced
async function gone(page, org) {
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    const left = await page.evaluate(`(() => {
        const page = document.querySelector(".cvat-team-analytics-page");
        const text = page.textContent;
        return [".cvat-team-analytics-definitions", ".cvat-team-analytics-definition", ".cvat-team-analytics-select-organization"]
            .filter((s) => document.querySelector(s))
            .concat(["One uninterrupted interval of job work", "Select an organization", "No organization selected", "owners and maintainers",
                "Started by hotkey"].filter((t) => text.includes(t)));
    })()`);
    check(!left.length, `still on the page: ${JSON.stringify(left)}`);
    log('no definitions block, no organization prompt, no "Started by hotkey / mouse" header');
}

// 6. the settings modal: it opens, lists the seeded Technical accounts by name, the picker finds a user of another
// organization, rows added and removed then Cancel send no PUT (and reopening shows the server's list), and a Save
// of the unchanged list answers and closes. A deleted user's "deleted account, id N" label is left to check-settings:
// its deleted-user part puts the list back without the deleted user, so none is listed when this step runs.
const MODAL = '.ant-modal.cvat-team-analytics-settings-modal';
const modalNames = (page) => page.evaluate(`[...document.querySelectorAll("${MODAL} .cvat-team-analytics-settings-account-name")].map((e) => e.textContent.trim())`);
const MODAL_CLOSED = `(() => { const m = document.querySelector("${MODAL}"); return !m || !m.checkVisibility(); })()`;

async function openModal(page, keys) {
    await clickSelectorIn(page, keys, '.cvat-team-analytics-header .cvat-team-analytics-settings-button');
    await page.waitFor(`!!document.querySelector("${MODAL}") && !document.querySelector("${MODAL} .cvat-team-analytics-settings-loading")`, 'the settings modal', 30000);
}

async function settingsModal(page, keys, api, org, seeded, other) {
    await openTA(page, org, `period=week`);
    await overviewReady(page, 'the week');
    let from = api.length;
    await openModal(page, keys);
    const modal = await page.evaluate(`(() => { const m = document.querySelector("${MODAL}");
        return { title: m.querySelector(".ant-modal-title")?.textContent.trim(), failed: !!m.querySelector(".cvat-team-analytics-settings-load-failed") }; })()`);
    const names = await modalNames(page);
    log(`settings modal "${modal.title}": accounts ${JSON.stringify(names)}; requests ${JSON.stringify(api.slice(from).map((r) => `${r.method} ${r.path}`))}`);
    check(modal.title === 'Team Analytics settings' && !modal.failed, `the settings modal: ${JSON.stringify(modal)}, expected "Team Analytics settings", loaded`);
    check(api.slice(from).some((r) => r.method === 'GET' && r.path.endsWith('/settings')), 'opening the modal sent no GET settings');
    check(JSON.stringify([...names].sort()) === JSON.stringify([...seeded].sort()),
        `the modal lists ${JSON.stringify(names)}, expected the seeded ${JSON.stringify(seeded)}`);

    // the picker finds a user of another organization than the one selected; it is added, then removed
    from = api.length;
    await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-picker`);
    await page.send('Input.insertText', { text: other });
    const option = `[...document.querySelectorAll(".cvat-team-analytics-settings-picker-dropdown .ant-select-item-option")].findIndex((o) => o.textContent.trim().split(" ")[0] === ${JSON.stringify(other)})`;
    await page.waitFor(`${option} >= 0`, `${other} offered by the picker`, 15000);
    const searched = api.slice(from).filter((r) => r.path.endsWith('/settings/users')).map((r) => r.query.get('search'));
    await clickSelectorIn(page, keys, '.cvat-team-analytics-settings-picker-dropdown .ant-select-item-option', await page.evaluate(option));
    await page.waitFor(`[...document.querySelectorAll("${MODAL} .cvat-team-analytics-settings-account-name")].some((e) => e.textContent.trim() === ${JSON.stringify(other)})`, `${other} added as a row`, 10000);
    if (SHOTS) await page.screenshot(`page-${org}-settings-picked`);
    await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-remove[aria-label="Remove ${other}"]`);
    const afterRemove = await modalNames(page);
    check(!afterRemove.includes(other), `${other} still listed after its remove button: ${JSON.stringify(afterRemove)}`);

    // an account already on the list is offered by the search, but disabled and marked "already on the list"; a
    // click on it adds no row
    check(seeded.length > 0, 'TA_TECHNICAL_ACCOUNTS names no account: nothing on the list to find in the picker');
    const listed = seeded[0];
    await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-picker`);
    await page.send('Input.insertText', { text: listed });
    const listedOption = `[...document.querySelectorAll(".cvat-team-analytics-settings-picker-dropdown .ant-select-item-option")].findIndex((o) => o.textContent.trim().split(" ")[0] === ${JSON.stringify(listed)})`;
    await page.waitFor(`${listedOption} >= 0`, `${listed} (on the list) offered by the picker`, 15000);
    const shown = await page.evaluate(`(() => { const o = [...document.querySelectorAll(".cvat-team-analytics-settings-picker-dropdown .ant-select-item-option")][${listedOption}];
        return { text: o.textContent.trim(), disabled: o.classList.contains("ant-select-item-option-disabled") && o.getAttribute("aria-disabled") !== "false",
            marked: !!o.querySelector(".cvat-team-analytics-settings-listed") }; })()`);
    check(shown.disabled && shown.marked && shown.text.endsWith('already on the list'),
        `${listed}, on the list, in the picker: ${JSON.stringify(shown)}, expected a disabled option marked "already on the list"`);
    await clickSelectorIn(page, keys, '.cvat-team-analytics-settings-picker-dropdown .ant-select-item-option', await page.evaluate(listedOption));
    await sleep(500);
    const afterListed = await modalNames(page);
    check(JSON.stringify([...afterListed].sort()) === JSON.stringify([...seeded].sort()),
        `a click on ${listed} (already on the list) changed the rows to ${JSON.stringify(afterListed)}, expected ${JSON.stringify(seeded)}`);
    log(`picker: ${listed} offered disabled, "${shown.text}"; a click on it adds no row`);
    await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-cancel`);
    await page.waitFor(MODAL_CLOSED, 'the modal closed by Cancel', 10000);
    const puts = api.slice(from).filter((r) => r.method === 'PUT');
    check(puts.length === 0, `adding and removing ${other} then Cancel sent ${puts.length} PUT requests, expected none`);
    log(`picker: searches ${JSON.stringify(searched)} found ${other} (another organization than ${org}); added, removed, Cancel: no PUT`);
    await openModal(page, keys);
    const reopened = await modalNames(page);
    check(JSON.stringify([...reopened].sort()) === JSON.stringify([...seeded].sort()), `reopened after Cancel the modal lists ${JSON.stringify(reopened)}, expected the server's ${JSON.stringify(seeded)}`);

    // Save of the unchanged list
    from = api.length;
    await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-save`);
    await page.waitFor(`(() => { const m = document.querySelector("${MODAL}");
        return !m || !m.checkVisibility() || !!m.querySelector(".cvat-team-analytics-settings-error"); })()`, 'the modal closed after Save', 30000);
    const error = await page.evaluate('document.querySelector(".cvat-team-analytics-settings-error")?.textContent.trim() || ""');
    check(!error, `the save failed: "${error}"`);
    const sent = api.slice(from).filter((r) => r.method === 'PUT' && r.path.endsWith('/settings'));
    check(sent.length === 1, `Save sent ${sent.length} PUT settings, expected one`);
    const saved = await page.evaluate('fetch("/api/team-analytics/settings").then((r) => r.json()).then((b) => b.technical_accounts.map((a) => a.user_name))');
    check(JSON.stringify([...saved].sort()) === JSON.stringify([...seeded].sort()), `after the save the list is ${JSON.stringify(saved)}`);
    log(`Save of the same list: one PUT, the modal closed with no error; the list is still ${JSON.stringify(saved)}`);
}

// 7. at instance scope (no organization selected) the project selector names projects of several organizations by
// their names, not "Project #N" (the names come from the fork's project-names lookup)
// The projects ORG's project selector names for the week (without "All projects" and "No project"), as the page
// itself shows them inside the organization: what instance scope must name too.
async function orgProjectNames(page, keys, org) {
    try {
        await openTA(page, org, `period=week`);
        await overviewReady(page, `the week of ${org}`);
        await openSelector(page, keys, 'project');
        await page.waitFor(OPTIONS_LOADED, `${org}'s project options loaded`, 30000);
    } catch (error) {
        // an organization with no work this week has no rows and no options: it names nothing
        log(`${org}: no project names this week (${error.message})`);
        return [];
    }
    const options = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-filter-popup li.cvat-team-analytics-filter-option[role=option]:not(.cvat-team-analytics-filter-option-all)")].map((o) => o.textContent.trim())');
    await keys.press('Escape');
    return options.filter((o) => o !== 'No project');
}

async function instanceNames(browser, orgs) {
    const page = await signIn(browser, 'ta-admin', '');
    const keys = input(page);
    await setWidth(page, 1400);
    // the names each organization's own selector shows this week; at least two organizations must have some, or
    // there is nothing to judge "names of several organizations in one list" by
    const byOrg = {};
    for (const org of orgs) byOrg[org] = await orgProjectNames(page, keys, org);
    const named = Object.entries(byOrg).filter(([, names]) => names.length);
    log(`project names this week by organization: ${JSON.stringify(Object.fromEntries(Object.entries(byOrg).map(([o, n]) => [o, n.length])))}`);
    check(named.length >= 2, `fewer than two of ${JSON.stringify(orgs)} have projects with work this week (${JSON.stringify(byOrg)}): `
        + 'the stack has no data for this part (run check-final first)');
    await openTA(page, '', 'period=week');
    await overviewReady(page, 'instance scope');
    const subtitle = await page.evaluate('document.querySelector(".cvat-team-analytics-heading")?.textContent || ""');
    check(subtitle.includes('All organizations and personal workspaces'), `the heading reads "${subtitle.trim()}", expected instance scope`);
    await openSelector(page, keys, 'project');
    await page.waitFor(OPTIONS_LOADED, 'instance scope project options loaded', 60000);
    const opened = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-filter-popup li.cvat-team-analytics-filter-option[role=option]")].map((o) => o.textContent.trim())');
    const numbered = opened.filter((o) => /^Project #\d+$/.test(o));
    // every organization's first name, found by its name at instance scope
    const missing = named.map(([org, names]) => [org, names[0]]).filter(([, name]) => !opened.includes(name));
    log(`instance scope: ${opened.length} project options, ${numbered.length} named "Project #N": ${JSON.stringify(opened.slice(0, 12))}`);
    check(!numbered.length && !missing.length, `instance scope project options: "Project #N" ${JSON.stringify(numbered)}, missing `
        + `${JSON.stringify(missing)} (organization, name its own selector shows); expected every project by name, those of `
        + `${named.map(([o]) => o).join(', ')} among them`);
    if (SHOTS) await page.screenshot('page-instance-project-selector');
}

// 8. screenshots for the evidence record at 1400 and 1024 px: the overview, the open project selector, a shown
// tooltip, the settings modal
async function screenshots(page, keys, org) {
    for (const width of [1400, 1024]) {
        await setWidth(page, width);
        await openTA(page, org, `period=week`);
        await overviewReady(page, 'the week');
        await fullShot(page, `page-${org}-${width}-overview`, width);
        await openSelector(page, keys, 'project');
        await page.screenshot(`page-${org}-${width}-project-selector`);
        await keys.press('Escape');
        await page.evaluate(`${TERMS}[4].scrollIntoView({block: "center"})`);
        await sleep(300);
        const r = await page.evaluate(`(() => { const b = ${TERMS}[4].getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; })()`);
        await keys.move(r.x, r.y);
        await sleep(800);
        await page.screenshot(`page-${org}-${width}-tooltip`);
        await keys.move(5, 5);
        await openModal(page, keys);
        await page.screenshot(`page-${org}-${width}-settings`);
        await clickSelectorIn(page, keys, `${MODAL} .cvat-team-analytics-settings-cancel`);
        await page.waitFor(MODAL_CLOSED, 'the modal closed by Cancel', 10000);
    }
    log(`screenshots at 1400 and 1024 px (overview, project selector, tooltip, settings) in ${SHOTS}`);
}

async function pageChecks(org) {
    const seeded = (process.env.TA_TECHNICAL_ACCOUNTS || '').split(/[\s,]+/).filter(Boolean);
    check(!!SHOTS, 'TA_SCREENSHOT_DIR must name a directory outside the repository for the screenshots');
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-fixes-'));
    let browser;
    try {
        browser = await launch(profile);
        const page = await signIn(browser, 'ta-admin', org);
        await page.send('Network.enable', {});
        const api = watchApi(browser, page);
        const keys = input(page);
        await filterBar(page, org);
        await widthSweep(page, org);
        await operationsTable(page);
        await gone(page, org);
        // the selectors need several projects and annotators with work this week: the volume organization (forty
        // projects, a hundred annotators, its current week loaded by check-final), also the longest list
        await selectors(page, keys, api, VOLUME_ORG);
        await popupFit(page, keys, VOLUME_ORG);
        await terms(page, keys, org);
        // a user of another organization than ORG for the picker: ta-org-b's owner
        await settingsModal(page, keys, api, org, seeded, 'ta-owner-b');
        await screenshots(page, keys, org);
        await instanceNames(browser, [...new Set([org, VOLUME_ORG, 'ta-org-a', 'ta-org-s'])]);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

const [phase, arg, option] = process.argv.slice(2);
const phases = { gestures, look, page: pageChecks };
if (!phases[phase] || !arg) {
    process.stderr.write('usage: fixes_browser.cjs gestures STATE | look ORG [split] | page ORG\n');
    process.exit(2);
}
phases[phase](arg, option === 'split').catch((error) => {
    process.stderr.write(`fixes browser check (${phase}) failed: ${error.message}\n`);
    process.exit(1);
});
