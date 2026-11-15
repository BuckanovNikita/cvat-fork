// Final run of Team Analytics in a real browser against the running stack (run.sh check-final).
// Headless Chrome over the DevTools protocol, with the helpers of browser_check.cjs.
//
//   node final_browser.cjs annotate STATE   ta-worker-c annotates the prepared job with the real UI:
//                                           draw (mouse, then the draw-mode hotkey), drag twice, copy
//                                           and paste, propagate, change a class by hotkey, delete,
//                                           run the detector twice from the AI tools (its model
//                                           list and answers supplied in the browser, see
//                                           superviseDetector), frame hotkeys, save, leave the
//                                           job. Writes what it did
//                                           into STATE (key "did") for final_run.py.
//   node final_browser.cjs page CONTEXT     the page: loads, period, both filters, a full view and
//                                           back, trends comparing two annotators, the overview's
//                                           length with 100 annotators and 40 long-named projects,
//                                           no overflow, a narrow window.
//   node final_browser.cjs service-down STATE   with the analytics worker at zero: the error panel (after
//                                           cvat-core's retries of 429), and the annotation view still
//                                           draws and saves.
//
// Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_BROWSER_BIN, TA_SCREENSHOT_DIR (optional).
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
    launch, signIn, check, sleep, log,
} = require('./browser_check.cjs');

const BASE = process.env.TA_BASE_URL;

// ---------------------------------------------------------------- input

const KEYS = {
    Control: { code: 'ControlLeft', keyCode: 17 },
    Delete: { code: 'Delete', keyCode: 46 },
};

function keyInfo(key) {
    if (KEYS[key]) return { key, ...KEYS[key] };
    if (/^[a-z]$/.test(key)) return { key, code: `Key${key.toUpperCase()}`, keyCode: key.toUpperCase().charCodeAt(0), text: key };
    if (/^[0-9]$/.test(key)) return { key, code: `Digit${key}`, keyCode: key.charCodeAt(0), text: key };
    throw new Error(`unknown key ${key}`);
}

function input(page) {
    const send = (method, params) => page.send(method, params);
    const mouse = async (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', {
        type, x, y, button: 'left', ...extra,
    });
    const move = async (x, y) => { await mouse('mouseMoved', x, y, { button: 'none' }); await sleep(250); };
    const click = async (x, y) => {
        await move(x, y);
        await mouse('mousePressed', x, y, { clickCount: 1, buttons: 1 });
        await mouse('mouseReleased', x, y, { clickCount: 1 });
        await sleep(400);
    };
    const drag = async (x, y, dx, dy) => {
        await move(x, y);
        await mouse('mousePressed', x, y, { clickCount: 1, buttons: 1 });
        for (let i = 1; i <= 6; i++) {
            await mouse('mouseMoved', x + (dx * i) / 6, y + (dy * i) / 6, { buttons: 1 });
            await sleep(40);
        }
        await mouse('mouseReleased', x + dx, y + dy, { clickCount: 1 });
        await sleep(600);
    };
    // a key, optionally with Control held; printable keys also type their character (keypress)
    const press = async (key, { ctrl = false } = {}) => {
        const info = keyInfo(key);
        const modifiers = ctrl ? 2 : 0;
        if (ctrl) await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, modifiers });
        const down = info.text && !ctrl ? { type: 'keyDown', text: info.text, unmodifiedText: info.text } : { type: 'rawKeyDown' };
        await send('Input.dispatchKeyEvent', {
            ...down, key: info.key, code: info.code, windowsVirtualKeyCode: info.keyCode, nativeVirtualKeyCode: info.keyCode, modifiers,
        });
        await send('Input.dispatchKeyEvent', {
            type: 'keyUp', key: info.key, code: info.code, windowsVirtualKeyCode: info.keyCode, nativeVirtualKeyCode: info.keyCode, modifiers,
        });
        if (ctrl) await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, modifiers: 0 });
        await sleep(600);
    };
    return { move, click, drag, press };
}

const rectOf = (page, selector) => page.evaluate(`(() => {
    const e = document.querySelector(${JSON.stringify(selector)});
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
})()`);

const shapeCount = (page) => page.evaluate('document.querySelectorAll(".cvat_canvas_shape").length');
const activated = (page) => page.evaluate('document.querySelector(".cvat_canvas_shape_activated")?.id || null');

const MODEL_RECORD = 'team_analytics:model_creation';

// every POST /api/events the page makes, with its status and the detector records in its body
function watchEventPosts(browser, page) {
    const posts = [];
    const requests = new Map();
    const recordsIn = (body) => {
        try {
            return (JSON.parse(body).events || []).filter((e) => e.obj_name === MODEL_RECORD)
                .map((e) => ({ count: e.count, payload: JSON.parse(e.payload || '{}'), job_id: e.job_id }));
        } catch { return null; }
    };
    browser.listeners.add((message) => {
        if (message.sessionId !== page.sessionId) return;
        if (message.method === 'Network.requestWillBeSent' && message.params.request.method === 'POST'
            && new URL(message.params.request.url).pathname === '/api/events') {
            const { requestId, request } = message.params;
            // a long body is left out of the event; it is fetched once the response is in
            requests.set(requestId, { url: request.url, body: request.postData ?? null });
        }
        if (message.method === 'Network.responseReceived' && requests.has(message.params.requestId)) {
            const { requestId } = message.params;
            const { url, body } = requests.get(requestId);
            const post = { url, status: message.params.response.status, model_records: body === null ? null : recordsIn(body) };
            if (body === null) {
                page.send('Network.getRequestPostData', { requestId })
                    .then(({ postData }) => { post.model_records = recordsIn(postData); })
                    .catch(() => { /* stays null: unknown */ });
            }
            posts.push(post);
        }
    });
    return posts;
}

// ---------------------------------------------------------------- detector

// The stack has no model function (nuclio is off; the server answers 503 for the model list). The
// browser's requests for the model list and for the model's answer are answered here, at the HTTP
// boundary; everything else (the AI tools control, the detector runner, the create thunk, the
// record and its POST /api/events) is the real UI against the real server. cvat-core makes exactly
// these requests for a detector run from the annotation view (server-proxy.ts):
//   HEAD /api/lambda/functions, GET /api/lambda/functions   the model list, once per page load
//   POST /api/lambda/functions/<id>                          the model's answer for one frame
// Any other /api/lambda/ request goes on to the server and is reported.
const MODEL = {
    id: 'ta-supplied-detector',
    name: 'Supplied detector',
    kind: 'detector',
    type: 'detector',
    description: 'model list entry supplied by the stack run',
    framework: 'none',
    labels_v2: [
        { name: 'box', type: 'any', attributes: [] },
        { name: 'other', type: 'any', attributes: [] },
    ],
};

// The model's answers, in the order the runs ask: first nothing, then two rectangles and a polygon.
// The frames are 8 x 8 px (stack_api.py tiny_png); label ids are the job's.
function detectorAnswers(labelIds) {
    const { box, other } = labelIds;
    const shape = (type, labelId, points) => ({
        type, label_id: labelId, points, attributes: [], occluded: false, rotation: 0, elements: [],
    });
    return [
        { shapes: [], tags: [] },
        {
            shapes: [
                shape('rectangle', box, [1, 1, 3, 3]),
                shape('rectangle', other, [4, 4, 7, 7]),
                shape('polygon', box, [1, 5, 3, 5, 2, 7]),
            ],
            tags: [],
        },
    ];
}

function superviseDetector(browser, page, labelIds) {
    const answers = detectorAnswers(labelIds);
    const seen = { supplied: [], passed: [], calls: [] };
    const json = (value) => Buffer.from(JSON.stringify(value)).toString('base64');
    browser.listeners.add((message) => {
        if (message.sessionId !== page.sessionId || message.method !== 'Fetch.requestPaused') return;
        const { requestId, request } = message.params;
        const { pathname } = new URL(request.url);
        const fulfil = (body) => {
            seen.supplied.push({ method: request.method, path: pathname });
            return page.send('Fetch.fulfillRequest', {
                requestId,
                responseCode: 200,
                responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
                ...(body === undefined ? {} : { body: json(body) }),
            });
        };
        let done;
        if (pathname === '/api/lambda/functions' && request.method === 'HEAD') done = fulfil(undefined);
        else if (pathname === '/api/lambda/functions' && request.method === 'GET') done = fulfil([MODEL]);
        else if (pathname === `/api/lambda/functions/${MODEL.id}` && request.method === 'POST') {
            const answer = answers[Math.min(seen.calls.length, answers.length - 1)];
            let sent = null;
            try { sent = JSON.parse(request.postData || 'null'); } catch { /* reported as null */ }
            seen.calls.push({ request: sent, answered: answer.shapes.length + answer.tags.length });
            done = fulfil(answer);
        } else {
            seen.passed.push({ method: request.method, path: pathname });
            done = page.send('Fetch.continueRequest', { requestId });
        }
        done.catch((error) => { seen.passed.push({ method: request.method, path: pathname, error: error.message }); });
    });
    return seen;
}

const visible = (selector) => `[...document.querySelectorAll(${JSON.stringify(selector)})].some((e) => e.checkVisibility())`;
const TOOLS_POPOVER = '.cvat-tools-control-popover:not(.ant-popover-hidden)';

// The annotator opens the AI tools, the Auto-labeling tab, picks the model (once) and clicks Annotate.
async function runDetector(page, keys, seen) {
    const calls = seen.calls.length;
    const before = await shapeCount(page);
    if (!await page.evaluate(visible(TOOLS_POPOVER))) {
        const control = await rectOf(page, '.cvat-tools-control');
        await keys.click(control.cx, control.cy);
        await page.waitFor(visible(TOOLS_POPOVER), 'the AI tools popover');
    }
    const tab = await page.evaluate(`(() => {
        const t = [...document.querySelectorAll("${TOOLS_POPOVER} .ant-tabs-tab")].find((e) => e.textContent.trim() === "Auto-labeling");
        if (!t) return null;
        const r = t.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2, active: t.classList.contains("ant-tabs-tab-active") };
    })()`);
    check(tab, 'no Auto-labeling tab in the AI tools');
    if (!tab.active) {
        await keys.click(tab.x, tab.y);
        await sleep(500);
    }
    const runner = `${TOOLS_POPOVER} .cvat-run-model-content`;
    const chosen = await textOf(page, `${runner} .ant-select-selection-item`);
    if (chosen !== MODEL.name) {
        const select = await rectOf(page, `${runner} .ant-select-selector`);
        await keys.click(select.cx, select.cy);
        await page.waitFor(`[...document.querySelectorAll(".ant-select-item-option")].some((e) => e.textContent.trim() === ${JSON.stringify(MODEL.name)} && e.checkVisibility())`, 'the supplied model in the model list');
        const option = await page.evaluate(`(() => {
            const r = [...document.querySelectorAll(".ant-select-item-option")].find((e) => e.textContent.trim() === ${JSON.stringify(MODEL.name)} && e.checkVisibility()).getBoundingClientRect();
            return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        })()`);
        await keys.click(option.x, option.y);
        await page.waitFor(`document.querySelector("${runner} .ant-select-selection-item")?.textContent.trim() === ${JSON.stringify(MODEL.name)}`, 'the model chosen');
    }
    // the label mapper maps the model's labels to the job's labels of the same name on its own
    await page.waitFor(`document.querySelector("${runner} .cvat-inference-run-button") && !document.querySelector("${runner} .cvat-inference-run-button").disabled`, 'the Annotate button enabled');
    const mapped = await count(page, `${runner} .cvat-runner-label-mapping-row`);
    const button = await rectOf(page, `${runner} .cvat-inference-run-button`);
    await keys.click(button.cx, button.cy);
    const until = Date.now() + 30000;
    while (seen.calls.length === calls && Date.now() < until) await sleep(250);
    check(seen.calls.length === calls + 1, `Annotate made ${seen.calls.length - calls} model calls`);
    // the "Making a server request" modal closes once the objects are created
    await page.waitFor('![...document.querySelectorAll(".ant-modal-title")].some((e) => e.textContent.includes("Making a server request") && e.checkVisibility())', 'the detector to finish');
    const { answered } = seen.calls[calls];
    await page.waitFor(`document.querySelectorAll(".cvat_canvas_shape").length === ${before + answered}`, `${answered} detector objects on the canvas`);
    await sleep(1500);
    const after = await shapeCount(page);
    const errors = await count(page, '.ant-notification-notice-error');
    check(after === before + answered && errors === 0, `detector run: ${before} -> ${after} shapes for ${answered} answered, ${errors} error notices`);
    return { answered, shapes_before: before, shapes_after: after, mapped_labels: mapped };
}

async function openJob(page, ids) {
    await page.goto(`${BASE}/tasks/${ids.task_id}/jobs/${ids.job_id}`);
    await page.waitFor('!!document.querySelector("#cvat_canvas_background") && document.querySelector("#cvat_canvas_background").getBoundingClientRect().width > 0', 'the annotation canvas', 90000);
    await sleep(2500);
}

async function drawRectangle(page, keys, from, to, how) {
    if (how === 'mouse') {
        await page.evaluate('document.querySelector(".cvat-draw-rectangle-control").dispatchEvent(new MouseEvent("mouseover", {bubbles: true}))');
        const control = await rectOf(page, '.cvat-draw-rectangle-control');
        await keys.click(control.cx, control.cy);
        await page.waitFor('!!document.querySelector(".cvat-draw-rectangle-shape-button")', 'the draw popover');
        const button = await rectOf(page, '.cvat-draw-rectangle-shape-button');
        await keys.click(button.cx, button.cy);
    } else {
        await keys.move(from.x - 40, from.y - 40);
        await keys.press('n');
    }
    const before = await shapeCount(page);
    await keys.click(from.x, from.y);
    await keys.click(to.x, to.y);
    await page.waitFor(`document.querySelectorAll(".cvat_canvas_shape").length === ${before + 1}`, `rectangle drawn by ${how}`);
}

async function annotate(stateFile) {
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-final-'));
    let browser;
    const did = {
        drawn: 0, draw_methods: [], dragged: 0, alignments: 0, pasted: 0, pasted_objects: 0,
        propagated_events: 0, propagated: 0, class_changes: [], deleted: 0, deleted_objects: 0, hotkeys: {},
    };
    const hotkey = (action, n = 1) => { did.hotkeys[action] = (did.hotkeys[action] || 0) + n; };
    try {
        browser = await launch(profile);
        const page = await signIn(browser, state.worker, state.org);
        await page.send('Network.enable', {});
        const posts = watchEventPosts(browser, page);
        // before the job opens: the page load there fetches the model list
        const detector = superviseDetector(browser, page, state.ui.label_ids);
        await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/lambda/*', requestStage: 'Request' }] });
        await openJob(page, state.ui);
        const keys = input(page);
        const bg = await rectOf(page, '#cvat_canvas_background');
        const at = (fx, fy) => ({ x: bg.x + bg.w * fx, y: bg.y + bg.h * fy });

        // two boxes: the first from the controls sidebar, the second with the draw-mode hotkey
        await drawRectangle(page, keys, at(0.12, 0.12), at(0.37, 0.37), 'mouse');
        did.drawn += 1; did.draw_methods.push('mouse');
        await drawRectangle(page, keys, at(0.56, 0.52), at(0.87, 0.9), 'hotkey');
        did.drawn += 1; did.draw_methods.push('hotkey');
        hotkey('SWITCH_DRAW_MODE_STANDARD_CONTROLS');
        log(`drew 2 rectangles (mouse, hotkey N)`);

        // two drags of the first box in a row: one alignment
        let a = await rectOf(page, '#cvat_canvas_shape_1');
        await keys.drag(a.cx, a.cy, bg.w * 0.06, bg.h * 0.04);
        a = await rectOf(page, '#cvat_canvas_shape_1');
        await keys.drag(a.cx, a.cy, -bg.w * 0.04, bg.h * 0.05);
        did.dragged += 2; did.alignments += 1;
        log('dragged the first box twice');

        // copy and paste the first box
        a = await rectOf(page, '#cvat_canvas_shape_1');
        await keys.move(a.cx, a.cy);
        check(await activated(page) === 'cvat_canvas_shape_1', 'the first box is not activated for copying');
        await keys.press('c', { ctrl: true }); hotkey('COPY_SHAPE');
        await keys.press('v', { ctrl: true }); hotkey('PASTE_SHAPE');
        const pasteAt = at(0.56, 0.15);
        await keys.click(pasteAt.x, pasteAt.y);
        await page.waitFor('document.querySelectorAll(".cvat_canvas_shape").length === 3', 'the pasted box');
        did.pasted += 1; did.pasted_objects += 1;
        log('copied and pasted the first box');

        // propagate the second box: the dialog's default is three copies forward
        const b = await rectOf(page, '#cvat_canvas_shape_2');
        await keys.move(b.cx, b.cy);
        check(await activated(page) === 'cvat_canvas_shape_2', 'the second box is not activated for propagation');
        await keys.press('b', { ctrl: true }); hotkey('PROPAGATE_OBJECT');
        await page.waitFor('!!document.querySelector(".ant-modal .ant-btn-primary")', 'the propagate dialog');
        const copies = Number(await page.evaluate('document.querySelectorAll(".ant-modal .ant-input-number-input")[0].value'));
        const yes = await rectOf(page, '.ant-modal .ant-btn-primary');
        await keys.click(yes.cx, yes.cy);
        await page.waitFor('!document.querySelector(".ant-modal-wrap:not([style*=\\"display: none\\"]) .ant-btn-primary")', 'the dialog to close');
        did.propagated_events += 1; did.propagated += copies;
        log(`propagated the second box (${copies} copies)`);

        // change the class of the first box with the label hotkey Ctrl+2
        a = await rectOf(page, '#cvat_canvas_shape_1');
        await keys.move(a.cx, a.cy);
        check(await activated(page) === 'cvat_canvas_shape_1', 'the first box is not activated for the class change');
        await keys.press('2', { ctrl: true }); hotkey('SWITCH_LABEL_2');
        await page.waitFor(`[...document.querySelectorAll(".cvat-objects-sidebar-state-item")].some((e) => e.innerText.includes(${JSON.stringify(state.ui.labels[1])}))`, 'the new class');
        did.class_changes.push({ count: 1, input_method: 'hotkey' });
        log(`changed the first box's class to ${state.ui.labels[1]} (Ctrl+2)`);

        // delete the pasted box
        const pasted = await rectOf(page, '#cvat_canvas_shape_3');
        await keys.move(pasted.cx, pasted.cy);
        check(await activated(page) === 'cvat_canvas_shape_3', 'the pasted box is not activated for deletion');
        await keys.press('Delete'); hotkey('DELETE_OBJECT_STANDARD_WORKSPACE');
        await page.waitFor('document.querySelectorAll(".cvat-objects-sidebar-state-item").length === 2', 'the deletion');
        did.deleted += 1; did.deleted_objects += 1;
        log('deleted the pasted box');

        // the detector from the AI tools, by mouse only: first the model answers nothing, then
        // three objects (two rectangles and a polygon) on this frame
        const runs = [];
        for (let i = 0; i < 2; i++) runs.push(await runDetector(page, keys, detector));
        const tools = await rectOf(page, '.cvat-tools-control');
        await keys.click(tools.cx, tools.cy); // the click trigger closes the popover again
        await sleep(500);
        log(`detector: ran twice; answered ${runs.map((r) => r.answered).join(', ')} objects; shapes ${runs.map((r) => `${r.shapes_before} -> ${r.shapes_after}`).join(', ')}`);

        // frame hotkeys, then save
        await keys.move(bg.x - 150, bg.y + 20);
        for (const k of ['f', 'f', 'f', 'd', 'd']) await keys.press(k);
        hotkey('NEXT_FRAME', 3); hotkey('PREV_FRAME', 2);
        await keys.press('s', { ctrl: true }); hotkey('SAVE_JOB');
        await page.waitFor(`fetch("/api/jobs/${state.ui.job_id}/annotations").then((r) => r.json()).then((j) => j.shapes.length > 0)`, 'the saved annotations');
        did.boxes_in_job_after_save = await page.evaluate(`fetch("/api/jobs/${state.ui.job_id}/annotations").then((r) => r.json()).then((j) => j.shapes.filter((s) => s.type === "rectangle").length)`);
        // what the detector created, as the server stored it: objects with source "auto"
        const auto = await page.evaluate(`fetch("/api/jobs/${state.ui.job_id}/annotations").then((r) => r.json()).then((j) => {
            const shapes = j.shapes.filter((s) => s.source === "auto");
            return { objects: shapes.length + j.tags.filter((t) => t.source === "auto").length + j.tracks.filter((t) => t.source === "auto").length,
                rectangles: shapes.filter((s) => s.type === "rectangle").length };
        })`);
        log(`F x3, D x2, Ctrl+S: ${did.boxes_in_job_after_save} boxes saved in the job; detector objects saved ${JSON.stringify(auto)}`);
        await page.screenshot('final-annotation');

        // leave the job through the header: the view writes its last input summary
        const tasks = await rectOf(page, '.cvat-header-tasks-button');
        await keys.click(tasks.cx, tasks.cy);
        await page.waitFor('location.pathname === "/tasks"', 'the tasks page');
        // The summary written as the job closes must leave with the closing save, well before CVAT's
        // next periodic save (90 s): the browser closes a few seconds after leaving, as a person
        // closing the tab would, and check-ui-records then looks for the summary.
        await sleep(5000);
        did.event_posts = posts;
        did.detector = {
            model: MODEL.id, runs, calls: detector.calls, supplied: detector.supplied, passed: detector.passed,
            created: auto,
        };
        log(`left the job; ${posts.length} POST /api/events: ${JSON.stringify(posts.map((p) => p.status))}`);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
    state.did = did;
    fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
}

// ---------------------------------------------------------------- page

// Elements that stick out of their card horizontally, unless an ancestor inside the card clips or
// scrolls them; and text cut without an ellipsis.
const OVERFLOW = `(() => {
    const out = [];
    const clips = (e) => ['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(e).overflowX);
    for (const card of document.querySelectorAll(".cvat-team-analytics-page .cvat-team-analytics-card")) {
        const box = card.getBoundingClientRect();
        for (const e of card.querySelectorAll("*")) {
            const r = e.getBoundingClientRect();
            if (!r.width || !e.checkVisibility() || (r.left >= box.left - 1 && r.right <= box.right + 1)) continue;
            let p = e.parentElement, clipped = false;
            while (p && p !== card) { if (clips(p)) { clipped = true; break; } p = p.parentElement; }
            if (!clipped) out.push((e.className && e.className.baseVal === undefined ? e.className : e.tagName) + " in " + card.className);
        }
    }
    if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push("page scrolls sideways: " + document.documentElement.scrollWidth + " > " + window.innerWidth);
    return out.slice(0, 10);
})()`;

const pageHeight = (page) => page.evaluate('document.querySelector(".cvat-team-analytics-page").scrollHeight');
const search = (page) => page.evaluate('location.search');
const textOf = (page, selector) => page.evaluate(`document.querySelector(${JSON.stringify(selector)})?.textContent.trim() || ""`);
const count = (page, selector) => page.evaluate(`document.querySelectorAll(${JSON.stringify(selector)}).length`);

async function clickSelector(page, keys, selector, index = 0) {
    await page.waitFor(`document.querySelectorAll(${JSON.stringify(selector)}).length > ${index}`, selector);
    await page.evaluate(`document.querySelectorAll(${JSON.stringify(selector)})[${index}].scrollIntoView({block: "center"})`);
    await sleep(300);
    const r = await page.evaluate(`(() => { const b = document.querySelectorAll(${JSON.stringify(selector)})[${index}].getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; })()`);
    await keys.click(r.x, r.y);
}

async function clickText(page, keys, selector, text) {
    const index = await page.evaluate(`[...document.querySelectorAll(${JSON.stringify(selector)})].findIndex((e) => e.textContent.trim() === ${JSON.stringify(text)})`);
    check(index >= 0, `no ${selector} reading "${text}"`);
    await clickSelector(page, keys, selector, index);
}

async function overviewReady(page, what) {
    await page.waitFor('!!document.querySelector(".cvat-team-analytics-annotator-row") && !document.querySelector(".cvat-team-analytics-pending") && !document.querySelector(".cvat-team-analytics-loading")', what, 90000);
    await sleep(1500);
}

const ANNOTATORS_VALUE = '.cvat-team-analytics-annotators .cvat-team-analytics-headline-value';

async function pageChecks(contextFile) {
    const context = JSON.parse(fs.readFileSync(contextFile, 'utf8'));
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-final-'));
    let browser;
    const result = {};
    try {
        browser = await launch(profile);

        // a small organization first: the overview's length with one annotator and one project
        const small = await signIn(browser, 'ta-owner-c', context.ui_org);
        await small.goto(`${BASE}/team-analytics`);
        await overviewReady(small, 'the overview of ta-org-c');
        result.small_height = await pageHeight(small);

        // the real UI's work of this run, as the page shows it for its project (all shapes)
        const { ui, did, model } = context;
        // filters are applied only in the organization the address names
        await small.goto(`${BASE}/team-analytics?period=week&project=${ui.project_id}&org=${context.ui_org}&shapes=all`);
        await overviewReady(small, `the overview of project ${ui.project_id}`);
        const shown = await small.evaluate(`(() => {
            const cells = (selector) => [...document.querySelectorAll(selector)].map((r) => [...r.children].map((c) => c.textContent.trim()));
            const value = (selector) => document.querySelector(selector)?.textContent.trim();
            return {
                operations: Object.fromEntries(cells(".cvat-team-analytics-operations tbody tr").map((r) => [r[0], r[1]])),
                methods: Object.fromEntries(cells(".cvat-team-analytics-method-row, .cvat-team-analytics-model-row").map((r) => [r[0], r[2]])),
                created: value(".cvat-team-analytics-objects-created .cvat-team-analytics-headline-value"),
                sessions: value(".cvat-team-analytics-sessions .cvat-team-analytics-headline-value"),
                hotkeys: [...document.querySelectorAll(".cvat-team-analytics-keyboard-figure")].map((e) => e.innerText.replace(/\\s+/g, " ")),
            };
        })()`);
        const want = {
            operations: {
                Creation: String(did.drawn + did.pasted_objects + did.propagated), Alignment: String(did.alignments),
                'Class change': String(did.class_changes.reduce((n, c) => n + c.count, 0)), Deletion: String(did.deleted_objects),
            },
            methods: { Drawn: String(did.drawn), Pasted: String(did.pasted_objects), Propagated: String(did.propagated), Model: String(model) },
            created: String(did.drawn + did.pasted_objects + did.propagated),
            sessions: '1',
        };
        const pressed = Object.values(did.hotkeys).reduce((a, b) => a + b, 0);
        await small.screenshot('final-real-ui-project');
        check(JSON.stringify({ ...shown, hotkeys: undefined }) === JSON.stringify({ ...want, hotkeys: undefined }),
            `the page shows ${JSON.stringify(shown)}, expected ${JSON.stringify(want)}`);
        check(shown.hotkeys.some((text) => text.includes(`Hotkey actions ${pressed}`)), `keyboard figures ${JSON.stringify(shown.hotkeys)}, ${pressed} hotkeys pressed`);
        log(`real UI figures on the page (project ${ui.project_id}): ${JSON.stringify(shown.operations)}, methods ${JSON.stringify(shown.methods)}, hotkey actions ${pressed}`);

        const page = await signIn(browser, 'ta-owner-v', context.volume_org);
        const keys = input(page);
        await page.goto(`${BASE}/team-analytics`);
        await overviewReady(page, 'the overview of ta-org-v');
        check(await textOf(page, ANNOTATORS_VALUE) === '100', `active annotators read "${await textOf(page, ANNOTATORS_VALUE)}"`);
        const rows = await count(page, '.cvat-team-analytics-annotator-row');
        const projectRows = await count(page, '.cvat-team-analytics-working-time-by-project .cvat-team-analytics-breakdown-row');
        const restTexts = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-rest")].map((e) => e.textContent.trim())');
        result.volume_height = await pageHeight(page);
        const overflow = await page.evaluate(OVERFLOW);
        await page.screenshot('final-volume-overview');
        check(rows === 8 && projectRows === 8, `rows by annotator ${rows}, by project ${projectRows}`);
        // project names come from CVAT (the page looks them up), long names included
        const projectNames = await page.evaluate('[...document.querySelectorAll(".cvat-team-analytics-working-time-by-project .cvat-team-analytics-breakdown-row .cvat-team-analytics-name")].map((e) => e.textContent.trim())');
        check(projectNames.length === 8 && projectNames.every((name) => name.startsWith('Volume project') && name.length > 80),
            `project names on the page ${JSON.stringify(projectNames)}`);
        check(restTexts.some((t) => t.startsWith('92 more')) && restTexts.some((t) => t.startsWith('32 more')), `remainder lines ${JSON.stringify(restTexts)}`);
        check(overflow.length === 0, `overflow at 1400 px: ${JSON.stringify(overflow)}`);
        check(result.volume_height <= result.small_height * 1.5,
            `the overview grew from ${result.small_height} px (1 annotator) to ${result.volume_height} px (100 annotators)`);
        log(`page loads: 100 active annotators, 8 + "92 more" annotators, 8 + "32 more" projects; height ${result.volume_height} px (ta-org-c: ${result.small_height} px); no overflow`);

        // period
        await clickText(page, keys, '.cvat-team-analytics-period', 'Year');
        await page.waitFor('location.search.includes("period=year")', 'period=year in the address');
        await overviewReady(page, 'the year');
        const yearRange = await textOf(page, '.cvat-team-analytics-range-label');
        const yearBars = await count(page, '.cvat-team-analytics-time-bar');
        check(yearBars >= 50, `year chart has ${yearBars} bars`);
        await clickText(page, keys, '.cvat-team-analytics-period', 'Week');
        await page.waitFor('!location.search.includes("period=year")', 'back to the week');
        await overviewReady(page, 'the week again');
        log(`period: Year (${yearRange}, ${yearBars} weekly bars) and back to Week`);

        // project filter, then the annotator filter
        await clickSelector(page, keys, '.cvat-team-analytics-working-time-by-project .cvat-team-analytics-breakdown-row');
        await page.waitFor('location.search.includes("project=")', 'project= in the address');
        await overviewReady(page, 'the project filter');
        const inProject = Number(await textOf(page, ANNOTATORS_VALUE));
        check(inProject >= 2 && inProject <= 3, `annotators in one project: ${inProject}`);
        await clickSelector(page, keys, '.cvat-team-analytics-annotator-row');
        await page.waitFor('location.search.includes("annotator=")', 'annotator= in the address');
        await overviewReady(page, 'the annotator filter');
        const one = await textOf(page, ANNOTATORS_VALUE);
        check(one === `1 of ${inProject}`, `annotators under both filters: ${one}`);
        const filtered = await search(page);
        await page.screenshot('final-filters');
        while (await count(page, '.cvat-team-analytics-filter-clear')) {
            await clickSelector(page, keys, '.cvat-team-analytics-filter-clear');
            await sleep(800);
        }
        await page.waitFor('!location.search.includes("project=") && !location.search.includes("annotator=")', 'filters cleared');
        await overviewReady(page, 'filters cleared');
        check(await textOf(page, ANNOTATORS_VALUE) === '100', 'annotators after clearing the filters');
        log(`filters: project -> ${inProject} annotators, + annotator -> 1 (${filtered}); cleared -> 100`);

        // full view of the annotators and back
        await clickSelector(page, keys, '.cvat-team-analytics-working-time-by-annotator .cvat-team-analytics-full-view-button');
        await page.waitFor('location.search.includes("view=annotators") && document.querySelectorAll(".cvat-team-analytics-full-list-row").length > 0', 'the full view');
        await sleep(1500);
        const listed = await count(page, '.cvat-team-analytics-full-list-row');
        const fullOverflow = await page.evaluate(OVERFLOW.replaceAll('.cvat-team-analytics-card', '.cvat-team-analytics-full-view'));
        await page.screenshot('final-full-view');
        check(listed === 100, `full view lists ${listed} annotators`);
        check(fullOverflow.length === 0, `overflow in the full view: ${JSON.stringify(fullOverflow)}`);
        await clickSelector(page, keys, '.cvat-team-analytics-full-back');
        await page.waitFor('!location.search.includes("view=")', 'back to the overview');
        await overviewReady(page, 'the overview after the full view');
        log(`full view: ${listed} annotators listed, no overflow; "Back to overview" returns`);

        // trends comparing two annotators
        for (const n of ['001', '002']) {
            await page.evaluate('document.querySelector(".cvat-team-analytics-compare-search").scrollIntoView({block: "center"})');
            const box = await rectOf(page, '.cvat-team-analytics-compare-search');
            await keys.click(box.cx, box.cy);
            await page.evaluate('document.querySelector(".cvat-team-analytics-compare-search").select()');
            await page.send('Input.insertText', { text: `annotator-${n}` });
            await sleep(800);
            await clickSelector(page, keys, '.cvat-team-analytics-compare-offer');
            await sleep(800);
        }
        await page.waitFor('document.querySelectorAll(".cvat-team-analytics-compare-chip").length === 2', 'two compared annotators');
        await page.waitFor('document.querySelector(".cvat-team-analytics-trend-chart")?.querySelectorAll(".cvat-team-analytics-trend-line").length === 2', 'two trend lines', 60000);
        const legend = await page.evaluate('[...document.querySelector(".cvat-team-analytics-trend-chart").querySelectorAll(".cvat-team-analytics-trend-legend-name")].map((e) => e.textContent.trim())');
        check(legend.length === 2 && legend[0].includes('001') && legend[1].includes('002'), `trend legend ${JSON.stringify(legend)}`);
        await page.screenshot('final-trends-compare');
        log(`trends: two lines, legend ${JSON.stringify(legend.map((name) => name.slice(0, 24)))}`);

        // narrow window: cards stack, wide tables scroll sideways, nothing overflows
        await page.send('Emulation.setDeviceMetricsOverride', { width: 400, height: 900, deviceScaleFactor: 1, mobile: false });
        // the trend values tables are folded away; open them, they hold a column per compared line
        await page.evaluate(`document.querySelectorAll("details.cvat-team-analytics-trend-values").forEach((d) => { d.open = true; })`);
        await sleep(2000);
        const narrow = await page.evaluate(`(() => {
            const cards = [...document.querySelectorAll(".cvat-team-analytics-cards > .cvat-team-analytics-card, .cvat-team-analytics-cards > * > .cvat-team-analytics-card")]
                .filter((c) => c.getBoundingClientRect().width > 0);
            const lefts = new Set(cards.map((c) => Math.round(c.getBoundingClientRect().left)));
            const tables = [...document.querySelectorAll(".cvat-team-analytics-table-scroll")].map((t) => ({
                overflow: getComputedStyle(t).overflowX, scrolls: t.scrollWidth > t.clientWidth + 1,
            }));
            const box = document.querySelector(".cvat-team-analytics-page").getBoundingClientRect();
            return { cards: cards.length, lefts: [...lefts], tables, page: [Math.round(box.left), Math.round(box.right)],
                app: document.documentElement.scrollWidth };
        })()`);
        // CVAT itself (#root, header) stays at least 1024 px wide; the page has to fit the window inside it
        const narrowOverflow = (await page.evaluate(OVERFLOW)).filter((item) => !item.startsWith('page scrolls sideways'));
        await page.screenshot('final-narrow');
        check(narrow.page[0] >= 0 && narrow.page[1] <= 400, `the page at 400 px spans ${JSON.stringify(narrow.page)}`);
        check(narrow.cards >= 5 && narrow.lefts.length === 1, `cards at 400 px: ${JSON.stringify(narrow)}`);
        check(narrow.tables.length > 0 && narrow.tables.every((t) => ['auto', 'scroll'].includes(t.overflow))
            && narrow.tables.some((t) => t.scrolls), `tables at 400 px: ${JSON.stringify(narrow.tables)}`);
        check(narrowOverflow.length === 0, `overflow at 400 px: ${JSON.stringify(narrowOverflow)}`);
        log(`narrow window (400 px): page within the window, ${narrow.cards} cards in one column, `
            + `${narrow.tables.filter((t) => t.scrolls).length}/${narrow.tables.length} tables scroll sideways, nothing out of its card `
            + `(CVAT's own header keeps the app ${narrow.app} px wide)`);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

// ---------------------------------------------------------------- analytics worker at zero

async function serviceDown(stateFile) {
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-final-'));
    let browser;
    try {
        browser = await launch(profile);
        const owner = await signIn(browser, 'ta-owner-c', state.org);
        const opened = Date.now();
        await owner.goto(`${BASE}/team-analytics`);
        const panel = await owner.waitFor('document.querySelector(".cvat-team-analytics-error")?.textContent.trim()', 'the error panel', 90000);
        const panelAfterS = ((Date.now() - opened) / 1000).toFixed(1);
        await owner.screenshot('final-service-down');
        check(panel.includes('could not be loaded'), `error panel reads "${panel}"`);
        log(`analytics worker at zero: the page shows "${panel.slice(0, 70)}" ${panelAfterS} s after it was opened`);

        const page = await signIn(browser, state.worker, state.org);
        await openJob(page, state.down);
        const keys = input(page);
        const bg = await rectOf(page, '#cvat_canvas_background');
        await drawRectangle(page, keys, { x: bg.x + bg.w * 0.2, y: bg.y + bg.h * 0.2 },
            { x: bg.x + bg.w * 0.6, y: bg.y + bg.h * 0.6 }, 'mouse');
        await keys.move(bg.x - 150, bg.y + 20);
        await keys.press('s', { ctrl: true });
        const saved = await page.waitFor(`fetch("/api/jobs/${state.down.job_id}/annotations").then((r) => r.json()).then((j) => j.shapes.length)`, 'the saved box');
        const errors = await count(page, '.ant-notification-notice-error');
        check(saved === 1 && errors === 0, `annotation with the analytics worker at zero: ${saved} shapes saved, ${errors} error notices`);
        log(`analytics worker at zero: ${state.worker} drew and saved a box in job ${state.down.job_id} (${saved} shape on the server, no error notice)`);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

const [phase, file] = process.argv.slice(2);
const phases = { annotate, page: pageChecks, 'service-down': serviceDown };
if (!phases[phase] || !file) {
    process.stderr.write('usage: final_browser.cjs annotate|page|service-down FILE\n');
    process.exit(2);
}
phases[phase](file).catch((error) => {
    process.stderr.write(`final browser check (${phase}) failed: ${error.message}\n`);
    process.exit(1);
});
