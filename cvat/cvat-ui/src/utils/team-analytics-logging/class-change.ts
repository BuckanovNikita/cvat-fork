// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Class change: an existing object gets a different label. CVAT records nothing for it, so every place
// of the 2D annotation view that changes the label of existing objects calls `recordClassChange` just
// BEFORE it assigns the new label (afterwards the old label is gone). One record per change, counting
// only the objects whose label differs from the new one and is not locked; a change back is another record.
//
// The input method is given by the call site, which knows it: a label hotkey is `hotkey`, a label picked
// in a sidebar or menu select is `mouse`.

import { InputMethod, PAYLOAD, RECORD } from './contract';
import { guarded } from './guard';
import {
    LoggedObject, LoggingJob, logRecord, objectShapeFields,
} from './record';

export interface LabelledObject extends LoggedObject {
    label?: { id?: number | null } | null;
    lock?: boolean;
}

export function recordClassChange(
    job: LoggingJob | null | undefined,
    objects: readonly (LabelledObject | null | undefined)[],
    label: { id?: number | null } | null | undefined,
    inputMethod: InputMethod,
): void {
    guarded(undefined, () => {
        if (!label || !Number.isInteger(label.id)) return;
        // cvat-core discards every change to a locked object, so its label stays as it was
        const changed = objects.filter((object) => !!object && !object.lock && object.label?.id !== label.id);
        if (!changed.length) return;
        // shape fields only: the input method is the call site's, and a drawing in progress keeps its own
        const fields = objectShapeFields(job, changed);
        logRecord(job, RECORD.classChange, { ...fields, [PAYLOAD.inputMethod]: inputMethod }, changed.length);
    });
}
