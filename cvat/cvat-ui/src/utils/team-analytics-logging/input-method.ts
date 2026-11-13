// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The one place that supplies `input_method` to the operation and alignment fields (and to any record
// that names the method that started an action, such as a class change).
//
// The method of an action is that of the step that started it:
//   - a shortcut handler that ran marks 'hotkey' (input-summary.ts, from the shortcut dispatcher);
//   - a click outside the canvas and outside a dialog marks 'mouse'. Canvas clicks place and edit
//     objects and never change the mark; a click in a confirmation dialog (delete, propagate) only
//     confirms the action already started, so it keeps the mark;
//   - drawing (draw, paste) takes the mark when the canvas reports the start of drawing and keeps it
//     until the drawn object is logged, whatever finishes it. A drawing that continues by itself after
//     the previous one takes the mark current at that moment.
// Without any mark the method is 'mouse'. Drags and resizes happen on the canvas: always 'mouse'.

import { InputMethod, PAYLOAD } from './contract';

export type ActionKind = 'operation' | 'alignment';

let mark: InputMethod | null = null;
let drawing: InputMethod | null = null;

export function markInput(method: InputMethod): void {
    mark = method;
}

/** The canvas started drawing (or pasting): the drawing keeps the method that started it. */
export function drawingStarted(): void {
    if (drawing === null) drawing = mark ?? 'mouse';
}

/** Drawing was cancelled: nothing it started is pending any more. */
export function drawingEnded(): void {
    drawing = null;
}

/** Forget every mark (another job was opened). */
export function resetInputMethod(): void {
    mark = null;
    drawing = null;
}

// The input method that started the action being logged. An operation ends a pending drawing.
export function currentInputMethod(kind: ActionKind): InputMethod {
    if (kind === 'alignment') return 'mouse';
    const method = drawing ?? mark ?? 'mouse';
    drawing = null;
    return method;
}

export function inputMethodFields(kind: ActionKind): Record<string, string> {
    return { [PAYLOAD.inputMethod]: currentInputMethod(kind) };
}
