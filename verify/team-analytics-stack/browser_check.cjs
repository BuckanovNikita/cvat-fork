// Team Analytics page in a real browser against the running stack (run.sh check-tracer).
// A headless Chrome is driven over the DevTools protocol with Node's own WebSocket, so nothing
// is installed. Each account signs in through CVAT's login form in a fresh browser context.
//
//   the maintainer of ta-org-a sees the header link, opens the page and reads the figures;
//   the worker of ta-org-a sees no link, gets "not available" on a direct visit and a refusal
//   from the service when the browser calls it with the worker's session.
//
// Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_BROWSER_BIN (google-chrome),
// TA_SCREENSHOT_DIR (optional: PNGs of what each account saw).
'use strict';

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const BASE = process.env.TA_BASE_URL;
const PASSWORD = process.env.TA_SEED_PASSWORD;
const BROWSER = process.env.TA_BROWSER_BIN || 'google-chrome';
const SHOTS = process.env.TA_SCREENSHOT_DIR || '';
const ORG = 'ta-org-a';
// stack_api.py WORK for ta-org-a, as the page formats hours
const EXPECTED_ROWS = [['ta-worker', '1.5 h'], ['ta-supervisor', '0.5 h']];

const log = (message) => process.stdout.write(`  ${message}\n`);
const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

async function launch(profile) {
    const chrome = spawn(BROWSER, [
        '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--disable-background-networking', '--disable-extensions', '--remote-debugging-address=127.0.0.1',
        '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--window-size=1400,900', 'about:blank',
    ], { stdio: 'ignore', detached: true });
    const portFile = path.join(profile, 'DevToolsActivePort');
    let socket;
    try {
        for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await sleep(100);
        const [port, wsPath] = fs.readFileSync(portFile, 'utf8').trim().split('\n');
        socket = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
        await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
    } catch (error) {
        try { process.kill(-chrome.pid, 'SIGKILL'); } catch { /* gone */ }
        throw new Error(`could not start ${BROWSER}: ${error.message}`);
    }
    let nextId = 0;
    const pending = new Map();
    const listeners = new Set(); // DevTools events (final_browser.cjs watches network responses)
    socket.onmessage = ({ data }) => {
        const message = JSON.parse(data);
        if (message.method) listeners.forEach((listener) => listener(message));
        const waiter = pending.get(message.id);
        if (!waiter) return;
        pending.delete(message.id);
        if (message.error) waiter.reject(new Error(`${waiter.method}: ${message.error.message}`));
        else waiter.resolve(message.result);
    };
    const send = (method, params = {}, sessionId = undefined) => new Promise((resolve, reject) => {
        const id = ++nextId;
        pending.set(id, { resolve, reject, method });
        socket.send(JSON.stringify({ id, method, params, sessionId }));
    });
    // stops the whole browser process group and waits for it, so its profile can be removed
    const close = async () => {
        socket.close();
        const exited = chrome.exitCode !== null ? Promise.resolve()
            : new Promise((resolve) => { chrome.once('exit', resolve); });
        try { process.kill(-chrome.pid, 'SIGTERM'); } catch { /* already gone */ }
        const timer = setTimeout(() => { try { process.kill(-chrome.pid, 'SIGKILL'); } catch { /* gone */ } }, 5000);
        await exited;
        clearTimeout(timer);
    };
    return { send, close, chrome, listeners };
}

async function openPage(browser) {
    const { browserContextId } = await browser.send('Target.createBrowserContext');
    const { targetId } = await browser.send('Target.createTarget', { url: 'about:blank', browserContextId });
    const { sessionId } = await browser.send('Target.attachToTarget', { targetId, flatten: true });
    const send = (method, params) => browser.send(method, params, sessionId);
    await send('Page.enable');
    const evaluate = async (expression) => {
        const { result, exceptionDetails } = await send('Runtime.evaluate', {
            expression, awaitPromise: true, returnByValue: true,
        });
        if (exceptionDetails) throw new Error(`${expression}: ${exceptionDetails.exception?.description}`);
        return result.value;
    };
    const waitFor = async (expression, what, timeoutMs = 60000) => {
        const until = Date.now() + timeoutMs;
        for (;;) {
            const value = await evaluate(expression).catch(() => null);
            if (value) return value;
            if (Date.now() > until) throw new Error(`timed out waiting for ${what}`);
            await sleep(250);
        }
    };
    const goto = async (url) => {
        await send('Page.navigate', { url });
        await waitFor('document.readyState === "complete"', `load of ${url}`);
    };
    const type = async (selector, text) => {
        await waitFor(`!!document.querySelector(${JSON.stringify(selector)})`, selector);
        await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
        await send('Input.insertText', { text });
    };
    const screenshot = async (name) => {
        if (!SHOTS) return;
        const { data } = await send('Page.captureScreenshot', { format: 'png' });
        fs.mkdirSync(SHOTS, { recursive: true });
        fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, 'base64'));
    };
    return { evaluate, waitFor, goto, type, screenshot, send, sessionId };
}

const LINK = '[...document.querySelectorAll(".cvat-header a, .cvat-header button")]'
    + '.find((e) => e.textContent.trim() === "Team Analytics")';

// Signs in through the login form with ta-org-a (or `org`) as the organization CVAT opens with.
async function signIn(browser, username, org = ORG) {
    const page = await openPage(browser);
    await page.goto(`${BASE}/auth/login`);
    await page.evaluate(`localStorage.setItem("currentOrganization", ${JSON.stringify(org)})`);
    await page.type('#credential', username);
    await page.type('#password', PASSWORD);
    // CVAT throttles sign-ins (429), as after the volume's hundred: the form is sent again after a pause,
    // for up to five minutes in all
    const signedIn = 'location.pathname !== "/auth/login" && !!document.querySelector(".cvat-header")';
    for (let attempt = 1; ; attempt++) {
        await page.evaluate('document.querySelector(".cvat-credentials-action-button").click()');
        const done = await page.waitFor(signedIn, `${username} signed in`, 20000).catch(() => false);
        if (done) break;
        if (attempt >= 10) throw new Error(`${username} could not sign in after ${attempt} attempts`);
        log(`${username}: not signed in yet (attempt ${attempt}); sending the form again in 25 s`);
        await sleep(25000);
    }
    await page.waitFor(
        `document.querySelector(".cvat-header-menu-user-dropdown-organization")?.textContent.trim() === ${JSON.stringify(org)}`,
        `${username} in ${org}`,
    );
    return page;
}

function check(condition, message) {
    if (!condition) throw new Error(message);
}

async function maintainer(browser) {
    const page = await signIn(browser, 'ta-maintainer');
    const linkShownAfter = Date.now();
    await page.waitFor(`!!(${LINK})`, 'the Team Analytics link for ta-maintainer', 30000);
    const linkDelayMs = Date.now() - linkShownAfter;
    await page.evaluate(`(${LINK}).click()`);
    await page.waitFor('location.pathname === "/team-analytics"', 'the page route');
    const rows = await page.waitFor(`(() => {
        const rows = [...document.querySelectorAll(".cvat-team-analytics-annotator-row")].map((row) => [
            row.querySelector(".cvat-team-analytics-name").textContent.trim(),
            row.querySelector(".cvat-team-analytics-value").textContent.trim(),
        ]);
        return rows.length ? rows : null;
    })()`, 'working time rows');
    await page.screenshot('maintainer-team-analytics');
    check(JSON.stringify(rows) === JSON.stringify(EXPECTED_ROWS),
        `ta-maintainer sees ${JSON.stringify(rows)}, expected ${JSON.stringify(EXPECTED_ROWS)}`);
    log(`ta-maintainer: header link shown, page /team-analytics rows ${JSON.stringify(rows)}`);
    return linkDelayMs;
}

async function worker(browser, linkDelayMs) {
    const page = await signIn(browser, 'ta-worker');
    // the maintainer's link appeared linkDelayMs after the organization showed; wait well past it
    await sleep(Math.max(5000, 3 * linkDelayMs));
    check(!(await page.evaluate(`!!(${LINK})`)), 'ta-worker sees the Team Analytics link');
    await page.screenshot('worker-header');
    await page.goto(`${BASE}/team-analytics`);
    const denied = await page.waitFor(
        'document.querySelector(".cvat-team-analytics-denied")?.textContent.trim()', 'the not-available state',
    );
    await page.screenshot('worker-team-analytics');
    check(denied.includes('Team analytics is not available'), `ta-worker sees "${denied}"`);
    // the browser's own fetch sends Accept */*; CVAT's API answers 406 to a bare application/json
    const status = await page.evaluate(
        `fetch("/api/team-analytics/overview?period=week&tz=UTC&org=${ORG}").then((r) => r.status)`,
    );
    check(status === 403, `CVAT's analytics API answered ta-worker with ${status}`);
    log(`ta-worker: no header link, direct visit shows "${denied.slice(0, 60)}", API call ${status}`);
}

async function main() {
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ta-browser-'));
    let browser;
    try {
        browser = await launch(profile);
        const linkDelayMs = await maintainer(browser);
        await worker(browser, linkDelayMs);
    } finally {
        await browser?.close();
        fs.rmSync(profile, { recursive: true, force: true });
    }
}

module.exports = { launch, openPage, signIn, check, sleep, log };

if (require.main === module) {
    main().catch((error) => {
        process.stderr.write(`browser check failed: ${error.message}\n`);
        process.exit(1);
    });
}
