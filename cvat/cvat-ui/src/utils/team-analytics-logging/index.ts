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
//   logRecord(job, name, payload, count?) -> sends one `debug:info` record named `name` (RECORD) through
//                                    the job's logger, fire-and-forget (class change, model creation and
//                                    input summary records build on it)
//   recordClassChange(job, objects, label, inputMethod) -> class change record (class-change.ts)
//   recordModelCreation(job, objects) -> model creation record of a detector run (model-creation.ts)

import { EventScope } from 'cvat-logger';

import {
    MIXED, PAYLOAD, RECORD, RecordName, TAG,
} from './contract';
import { guarded, recordFailure, switchedOff } from './guard';
import { inputMethodFields } from './input-method';

export {
    INPUT_METHODS, MIXED, PAYLOAD, RECORD, SHAPE_TYPES, TAG,
} from './contract';
export type { InputMethod, RecordName } from './contract';

type Fields = Record<string, string | number>;

// What the module reads of an ObjectState (or of its serialized form).
export interface LoggedObject {
    clientID?: number | null;
    shapeType?: string | null;
    objectType?: string | null;
    frame?: number | null;
}

// What the module reads of the open job (a cvat-core Job).
export interface LoggingJob {
    dimension?: string;
    logger: { log(scope: string, payload?: Record<string, unknown>, wait?: boolean): Promise<unknown> };
}

type Objects = readonly (LoggedObject | null | undefined)[] | (() => readonly (LoggedObject | null | undefined)[]);

// Only the 2D canvas is instrumented; without an open job nothing is recorded.
function instrumented(job: LoggingJob | null | undefined): job is LoggingJob {
    return !!job && job.dimension === '2d' && !!job.logger;
}

function single(values: string[]): string {
    return new Set(values).size === 1 ? values[0] : MIXED;
}

function isInteger(value: unknown): value is number {
    return typeof value === 'number' && Number.isInteger(value);
}

// The shape fields of `objects`, or no fields when an object's kind is unknown.
function shapeFields(objects: readonly (LoggedObject | null | undefined)[]): Fields {
    if (!objects.length) return {};
    const shapeTypes: string[] = [];
    const objectTypes: string[] = [];
    let rectangles = 0;
    for (const object of objects) {
        if (!object || typeof object.objectType !== 'string') return {};
        const isTag = object.objectType === TAG;
        if (!isTag && typeof object.shapeType !== 'string') return {};
        shapeTypes.push(isTag ? TAG : object.shapeType as string);
        objectTypes.push(object.objectType);
        if (object.shapeType === 'rectangle' && object.objectType === 'shape') rectangles += 1;
    }
    return {
        [PAYLOAD.shapeType]: single(shapeTypes),
        [PAYLOAD.rectangleCount]: rectangles,
        [PAYLOAD.objectType]: single(objectTypes),
    };
}

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
        return { ...fields, ...inputMethodFields('alignment') };
    });
}

/**
 * Sends one `debug:info` record through the job's logger (so it carries project, task and job),
 * fire-and-forget. `count`, when given, must be an integer >= 0 and goes to the event's count column.
 */
export function logRecord(
    job: LoggingJob | null | undefined,
    name: RecordName,
    payload: Record<string, string | number | boolean | Record<string, number>> = {},
    count?: number,
): void {
    guarded(undefined, () => {
        if (!instrumented(job) || !Object.values(RECORD).includes(name)) return;
        const record: Record<string, unknown> = { ...payload, obj_name: name };
        if (count !== undefined) {
            if (!isInteger(count) || count < 0) return;
            record.count = count;
        }
        delete record.client_id;
        job.logger.log(EventScope.debugInfo, record).catch((error: unknown) => {
            if (!switchedOff()) recordFailure(error);
        });
    });
}

// Class change record (class-change.ts): call just before the new label is assigned.
export { recordClassChange } from './class-change';
// Model creation record (model-creation.ts): call right after the detector's objects are created.
export { recordModelCreation } from './model-creation';
