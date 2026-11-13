// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Class change: an existing object gets a different label. CVAT records nothing for it, so every place
// of the 2D annotation view that changes the label of existing objects calls `recordClassChange` just
// BEFORE it assigns the new label (afterwards the old label is gone). One record per change, counting
// only the objects whose label differs from the new one; a change back is another record.
//
// The input method is given by the call site, which knows it: a label hotkey is `hotkey`, a label picked
// in a sidebar or menu select is `mouse`.

import { InputMethod, PAYLOAD, RECORD } from './contract';
import { guarded } from './guard';
import {
    LoggedObject, LoggingJob, logRecord, operationFields,
} from './index';

export interface LabelledObject extends LoggedObject {
    label?: { id?: number | null } | null;
}

export function recordClassChange(
    job: LoggingJob | null | undefined,
    objects: readonly (LabelledObject | null | undefined)[],
    label: { id?: number | null } | null | undefined,
    inputMethod: InputMethod,
): void {
    guarded(undefined, () => {
        if (!label || !Number.isInteger(label.id)) return;
        const changed = objects.filter((object) => !!object && object.label?.id !== label.id);
        if (!changed.length) return;
        const fields = operationFields(job, changed);
        logRecord(job, RECORD.classChange, { ...fields, [PAYLOAD.inputMethod]: inputMethod }, changed.length);
    });
}
