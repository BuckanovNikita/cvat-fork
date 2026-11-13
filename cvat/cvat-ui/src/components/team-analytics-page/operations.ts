// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { OperationName, OperationRow, OperationsFigures } from './service';

// Each operation has one name and one colour everywhere on the page.
export interface OperationLook {
    name: string;
    color: string;
    // text colour on top of `color`
    ink: string;
}

export const OPERATION_LOOKS: Record<OperationName, OperationLook> = {
    creation: { name: 'Creation', color: '#2a78d6', ink: '#ffffff' },
    alignment: { name: 'Alignment', color: '#eb6834', ink: '#ffffff' },
    class_change: { name: 'Class change', color: '#1baf7a', ink: '#ffffff' },
    deletion: { name: 'Deletion', color: '#eda100', ink: '#0b0b0b' },
    other: { name: 'Other', color: '#c9c8c2', ink: '#0b0b0b' },
};

export function operationRow(figures: OperationsFigures, operation: OperationName): OperationRow | null {
    return figures.rows.find((row) => row.operation === operation) ?? null;
}

// In a legacy period class changes were not recorded: the page shows them as not recorded, not as zero.
export function isRecorded(figures: OperationsFigures, operation: OperationName): boolean {
    return !(figures.legacy && operation === 'class_change');
}

// No job work in the scope and period: no working time and no operation at all.
export function hasNoJobWork(figures: OperationsFigures): boolean {
    return figures.working_time_ms === 0 && figures.rows.every((row) => row.objects === 0);
}

// How the operation's objects were started: by hotkey or by mouse. Alignment is done on the canvas, so it
// is mouse only; in a legacy period the input method was not recorded; without any recorded start there
// is no split.
export type InputSplit =
    | { kind: 'split'; hotkey: number; mouse: number } // shares of the recorded starts
    | { kind: 'mouse-only' }
    | { kind: 'not-recorded' }
    | { kind: 'none' };

export function inputSplit(figures: OperationsFigures, row: OperationRow): InputSplit {
    if (row.operation === 'alignment') return { kind: 'mouse-only' };
    if (figures.legacy) return { kind: 'not-recorded' };
    const hotkey = row.hotkey_objects ?? 0;
    const mouse = row.mouse_objects ?? 0;
    if (hotkey + mouse === 0) return { kind: 'none' };
    return { kind: 'split', hotkey: hotkey / (hotkey + mouse), mouse: mouse / (hotkey + mouse) };
}
