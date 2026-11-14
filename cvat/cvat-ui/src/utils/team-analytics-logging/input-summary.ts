// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Hotkey actions and mouse actions inside the open job, counted in memory and sent as one input
// summary record (RECORD.inputSummary: `hotkeys` = action name -> count, `mouse` = zone -> count).
//
//   trackInputJob(job)    the annotation page opened `job`: counting starts (an earlier job's counts are
//                         written first)
//   untrackInputJob()     the job is closed: what was counted is written, counting stops
//   hotkeyUsed(action, event)  the shortcut dispatcher is about to run the handler of `action`
//   inputEvent(event)     every keydown and click the application's window listener sees
//
// A hotkey action is named by what the shortcut does, so a remapped key is the same action. A held
// key counts once (auto-repeats ignored), except frame navigation, where every invocation counts.
// A mouse action is a click on a control (button, menu item, sidebar control, ...), counted per zone
// of the page; clicks on the canvas are counted apart, under zone 'canvas'.
// The summary is written at most once a minute and only at a moment when the person acts (a key press
// or a click) or when the job is closed: never on a timer, because the server counts the time between
// two events as working time. Nothing is sent per hotkey action.

import { RECORD } from './contract';
import { guarded } from './guard';
import { markInput, resetInputMethod } from './input-method';
import type { LoggingJob } from './index';
import { logRecord } from './index';

export const SUMMARY_INTERVAL_MS = 60000;

// Shortcuts that move between frames: a held key moves on every invocation, and each counts.
export const FRAME_NAVIGATION_ACTIONS: ReadonlySet<string> = new Set([
    'NEXT_FRAME', 'PREV_FRAME', 'FORWARD_FRAME', 'BACKWARD_FRAME', 'NEXT_KEY_FRAME', 'PREV_KEY_FRAME',
    'SEARCH_FORWARD', 'SEARCH_BACKWARD', 'CHAPTER_FORWARD', 'CHAPTER_BACKWARD',
]);

// Zones of the annotation page, first match wins. Dialogs, popovers, dropdowns and menus render in
// portals outside the page's own areas, so they are zones of their own.
const ZONES: [string, string][] = [
    ['canvas', '.cvat-canvas-container'],
    ['modal', '.ant-modal-root, .ant-modal-wrap, .ant-modal'],
    ['popup', '.ant-popover, .ant-dropdown, .ant-select-dropdown, .ant-picker-dropdown, .ant-menu-submenu-popup, ' +
        '.ant-tooltip, .ant-notification, .ant-message, .cvat-canvas-context-menu'],
    ['header', '.cvat-annotation-header'],
    ['controls_sidebar', '.cvat-canvas-controls-sidebar'],
    ['objects_sidebar', '.cvat-objects-sidebar'],
];
const OTHER_ZONE = 'other';

// What counts as a control: an element a person clicks to make something happen.
const CONTROL = [
    'button', 'a[href]', 'input', 'select', 'textarea', 'label', 'summary',
    '[role="button"]', '[role="menuitem"]', '[role="menuitemcheckbox"]', '[role="menuitemradio"]',
    '[role="option"]', '[role="tab"]', '[role="checkbox"]', '[role="radio"]', '[role="switch"]',
    '[role="slider"]', '[role="combobox"]', '[role="treeitem"]',
    '.ant-btn', '.ant-select', '.ant-checkbox-wrapper', '.ant-radio-wrapper', '.ant-switch', '.ant-slider',
    '.ant-menu-item', '.ant-dropdown-menu-item', '.ant-select-item', '.ant-collapse-header', '.ant-tabs-tab',
    '.ant-input-number', '.anticon', '[tabindex]',
].join(', ');

interface Closest {
    closest(selectors: string): unknown;
}

let job: LoggingJob | null = null;
let hotkeys: Record<string, number> = {};
let mouse: Record<string, number> = {};
let lastWritten = 0;

function counted(): boolean {
    return Object.keys(hotkeys).length > 0 || Object.keys(mouse).length > 0;
}

function add(counts: Record<string, number>, name: string): void {
    counts[name] = (counts[name] ?? 0) + 1;
}

function write(): Promise<void> {
    const logged = job && counted() ? logRecord(job, RECORD.inputSummary, { hotkeys, mouse }) : Promise.resolve();
    hotkeys = {};
    mouse = {};
    lastWritten = Date.now();
    return logged;
}

// The person acts now: a summary is due when a minute has passed since the last one.
function active(): void {
    if (counted() && Date.now() - lastWritten >= SUMMARY_INTERVAL_MS) write();
}

function tracked(): boolean {
    return !!job && job.dimension === '2d';
}

function zoneOf(target: Closest): string {
    for (const [zone, selector] of ZONES) {
        if (target.closest(selector)) return zone;
    }
    return OTHER_ZONE;
}

function isElement(target: unknown): target is Closest {
    return !!target && typeof (target as Closest).closest === 'function';
}

export function trackInputJob(next: LoggingJob | null | undefined): void {
    guarded(undefined, () => {
        if (job === next) return;
        if (job) write();
        job = next ?? null;
        hotkeys = {};
        mouse = {};
        lastWritten = Date.now();
        resetInputMethod();
    });
}

// The returned promise settles (never rejects) once the logger holds the last summary: the annotation
// view saves the logs after it, so the summary leaves with the closing save.
export function untrackInputJob(): Promise<void> {
    return guarded(Promise.resolve(), () => {
        const logged = job ? write() : Promise.resolve();
        job = null;
        resetInputMethod();
        return logged;
    });
}

export function hotkeyUsed(action: string, event: { repeat?: boolean } | null | undefined): void {
    guarded(undefined, () => {
        if (!tracked()) return;
        markInput('hotkey');
        if (event?.repeat && !FRAME_NAVIGATION_ACTIONS.has(action)) return;
        add(hotkeys, action);
    });
}

export function inputEvent(event: { type?: string; target?: unknown } | null | undefined): void {
    guarded(undefined, () => {
        if (!tracked() || !event) return;
        active();
        if (event.type !== 'click' || !isElement(event.target)) return;
        const zone = zoneOf(event.target);
        if (zone === 'canvas') {
            add(mouse, zone);
            return;
        }
        // a click in a dialog confirms what was started before it
        if (zone !== 'modal') markInput('mouse');
        if (event.target.closest(CONTROL)) add(mouse, zone);
    });
}
