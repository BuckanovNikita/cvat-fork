// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Model creation: objects the built-in detector made in the annotation view. CVAT logs nothing for them,
// so the detector's call site calls `recordModelCreation` once the create thunk reports the objects
// created (never for objects that could not be created). One record per run: `count` = every object
// created, `rectangle_count` = the single-frame rectangles among them (the Model boxes). Nothing is sent
// when the detector made nothing.

import { PAYLOAD, RECORD } from './contract';
import { guarded } from './guard';
import { LoggedObject, LoggingJob, logRecord } from './record';

export function recordModelCreation(
    job: LoggingJob | null | undefined,
    objects: readonly (LoggedObject | null | undefined)[],
): void {
    guarded(undefined, () => {
        const created = objects.filter((object) => !!object) as LoggedObject[];
        if (!created.length) return;
        const rectangles = created
            .filter((object) => object.shapeType === 'rectangle' && object.objectType === 'shape').length;
        logRecord(job, RECORD.modelCreation, { [PAYLOAD.rectangleCount]: rectangles }, created.length);
    });
}
