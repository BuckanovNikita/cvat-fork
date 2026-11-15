// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import {
    OperationName, OperationRow, OperationsFigures, RowOperations,
} from './service';
import { formatHours } from './format';

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

// One part of a row's bar
export interface BarPart {
    key: string;
    color: string;
    // relative size of the part within the row's bar
    grow: number;
    title: string;
}

// The parts a row's bar is split into, in order: each operation and Other, class change left out in a legacy
// period (it was not recorded). The overview's bars and the full view's share them, and so their legends.
export function splitParts(legacy: boolean): OperationName[] {
    const operations: OperationName[] = ['creation', 'alignment', 'class_change', 'deletion'];
    return [...operations.filter((key) => !(legacy && key === 'class_change')), 'other'];
}

// The parts of the bar of row `name`: each part's time out of the row's operations.
export function operationParts(operations: RowOperations, name: string, legacy: boolean): BarPart[] {
    return splitParts(legacy).map((key) => {
        const look = OPERATION_LOOKS[key];
        const time = operations[key].time_ms;
        return {
            key, color: look.color, grow: time, title: `${name} · ${look.name}: ${formatHours(time)}`,
        };
    });
}

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
