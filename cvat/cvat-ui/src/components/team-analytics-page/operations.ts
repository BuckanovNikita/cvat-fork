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
