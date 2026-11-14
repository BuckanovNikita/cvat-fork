// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Team Analytics logging: what the 2D annotation view adds to the events CVAT already sends.
// One guarded entry point per kind of record; none of them can throw into the caller (guard.ts), and
// nothing is recorded outside an open 2D job.
//
//   operationFields(job, objects) -> fields to spread into the payload of the existing draw, paste,
//                                    propagate and delete events
//   alignmentFields(job, object)  -> the same plus the object reference and frame, for drag and resize
//                                    (and the group mark on the grabbed object's drag of a group move)
//   groupMoved(job, move)         -> sends the group move event (group-move.ts)
//   logRecord(job, name, payload, count?) -> sends one `debug:info` record named `name` (RECORD) through
//                                    the job's logger, fire-and-forget (class change, model creation and
//                                    input summary records build on it; record.ts)
//   listenForInput / trackInputJob / untrackInputJob / hotkeyUsed / inputEvent / frameRequested /
//                                    frameShown -> hotkey and mouse counting and the input summary record
//                                    (input-summary.ts)
//   drawingStarted / drawingEnded / currentInputMethod -> the input method of actions (input-method.ts)
//   recordClassChange(job, objects, label, inputMethod) -> class change record (class-change.ts)
//   recordModelCreation(job, objects) -> model creation record of a detector run (model-creation.ts)

import { PAYLOAD } from './contract';
import { guarded } from './guard';
import { grabbedFields } from './group-move';
import { inputMethodFields } from './input-method';
import {
    Fields, LoggedObject, LoggingJob, instrumented, isInteger, shapeFields,
} from './record';

export {
    INPUT_METHODS, MIXED, PAYLOAD, RECORD, SHAPE_TYPES, TAG,
} from './contract';
export type { InputMethod, RecordName } from './contract';
export {
    frameRequested, frameShown, hotkeyUsed, inputEvent, listenForInput, trackInputJob, untrackInputJob,
} from './input-summary';
export { drawingEnded, drawingStarted, currentInputMethod } from './input-method';
// Group move event (group-move.ts): call when the canvas reports a group move, before it is saved.
export { groupMoved } from './group-move';
export type { GroupMove } from './group-move';
// Writing a record, and what the module reads of a job and an object (record.ts).
export { logRecord, objectShapeFields } from './record';
export type { LoggedObject, LoggingJob } from './record';

type Objects = readonly (LoggedObject | null | undefined)[] | (() => readonly (LoggedObject | null | undefined)[]);

/** Fields for a draw, paste, propagate or delete event of `objects` (the objects its `count` counts). */
export function operationFields(job: LoggingJob | null | undefined, objects: Objects): Fields {
    return guarded({}, () => {
        if (!instrumented(job)) return {};
        const list = typeof objects === 'function' ? objects() : objects;
        const fields = shapeFields(list);
        return Object.keys(fields).length ? { ...fields, ...inputMethodFields('operation') } : {};
    });
}

/** Fields for a drag or resize event of `object`: its shape, its reference within the job and the frame. */
export function alignmentFields(job: LoggingJob | null | undefined, object: LoggedObject | null | undefined): Fields {
    return guarded({}, () => {
        if (!instrumented(job) || !object) return {};
        const fields: Fields = { ...shapeFields([object]) };
        if (isInteger(object.clientID)) fields[PAYLOAD.objectRef] = object.clientID;
        if (isInteger(object.frame)) fields[PAYLOAD.frame] = object.frame;
        return { ...fields, ...grabbedFields(object), ...inputMethodFields('alignment') };
    });
}

// Class change record (class-change.ts): call just before the new label is assigned.
export { recordClassChange } from './class-change';
// Model creation record (model-creation.ts): call once the detector's objects are known to be created.
export { recordModelCreation } from './model-creation';
