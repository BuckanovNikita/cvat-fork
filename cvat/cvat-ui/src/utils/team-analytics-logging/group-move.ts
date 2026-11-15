// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The group move event (contract.ts, GROUP): one `drag:object` for a gesture that moved several selected
// objects together, whether one of them was dragged or the selection box was moved. The canvas reports
// both as one group event; when the gesture began on an object, it then reports that object's own drag
// in the same task, which CVAT logs as before and `grabbedFields` marks as part of the group.

import { EventScope } from 'cvat-logger';

import { GROUP, PAYLOAD } from './contract';
import { guarded, recordFailure, switchedOff } from './guard';
import { inputMethodFields } from './input-method';
import {
    Fields, LoggedObject, LoggingJob, instrumented, isInteger, shapeFields,
} from './record';

// What the module reads of the canvas's group event (`canvas.groupmoved`).
export interface GroupMove {
    duration?: number;
    states: readonly { state: LoggedObject | null | undefined }[];
}

// The objects of the group just sent, until the end of the task that sent it: only a drag of one of them
// reported in that same task is the grabbed object's own drag.
let justMoved: Set<number> | null = null;

/** Sends the group event for `move`, fire-and-forget; call before the move is saved. */
export function groupMoved(job: LoggingJob | null | undefined, move: GroupMove | null | undefined): void {
    guarded(undefined, () => {
        if (!instrumented(job) || !move || !move.states.length) return;
        const objects = move.states.map((moved) => moved.state);
        const payload: Fields = {
            ...shapeFields(objects),
            [PAYLOAD.group]: GROUP.move,
            count: objects.length,
            ...inputMethodFields('alignment'),
        };
        const frame = objects[0]?.frame;
        if (isInteger(frame)) payload[PAYLOAD.frame] = frame;
        if (typeof move.duration === 'number') payload.duration = move.duration;
        const moved = new Set(objects.map((object) => object?.clientID).filter(isInteger));

        job.logger.log(EventScope.dragObject, payload).then(undefined, (error: unknown) => {
            if (!switchedOff()) recordFailure(error);
        });
        justMoved = moved;
        setTimeout(() => {
            if (justMoved === moved) justMoved = null;
        }, 0);
    });
}

/** The group mark for the drag of `object`, when it is the grabbed object of the group just sent. */
export function grabbedFields(object: LoggedObject): Fields {
    if (!justMoved || !isInteger(object.clientID) || !justMoved.has(object.clientID)) return {};
    justMoved = null;
    return { [PAYLOAD.group]: GROUP.grabbed };
}
