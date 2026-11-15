// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Writing a Team Analytics record, and what every part of the logging module reads of the open job and of
// an object. The record builders (class-change.ts, model-creation.ts, input-summary.ts) import from here,
// never from index.ts, so the module has no import cycle; index.ts re-exports the public part.

import { EventScope } from 'cvat-logger';

import {
    MIXED, PAYLOAD, RECORD, RecordName, TAG,
} from './contract';
import { guarded, recordFailure, switchedOff } from './guard';

export type Fields = Record<string, string | number>;

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

// Only the 2D canvas is instrumented; without an open job nothing is recorded.
export function instrumented(job: LoggingJob | null | undefined): job is LoggingJob {
    return !!job && job.dimension === '2d' && !!job.logger;
}

function single(values: string[]): string {
    return new Set(values).size === 1 ? values[0] : MIXED;
}

export function isInteger(value: unknown): value is number {
    return typeof value === 'number' && Number.isInteger(value);
}

// The shape fields of `objects`, or no fields when an object's kind is unknown.
export function shapeFields(objects: readonly (LoggedObject | null | undefined)[]): Fields {
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

/**
 * Only the shape fields of `objects`, for a record that names its input method itself (class change):
 * unlike `operationFields`, it leaves a pending drawing's input method in place.
 */
export function objectShapeFields(
    job: LoggingJob | null | undefined,
    objects: readonly (LoggedObject | null | undefined)[],
): Fields {
    return guarded({}, () => (instrumented(job) ? shapeFields(objects) : {}));
}

/**
 * Sends one `debug:info` record through the job's logger (so it carries project, task and job),
 * fire-and-forget. `count`, when given, must be an integer >= 0 and goes to the event's count column.
 * The returned promise settles (never rejects) once the logger holds the record, so a caller that saves
 * the logs right after can wait for it.
 */
export function logRecord(
    job: LoggingJob | null | undefined,
    name: RecordName,
    payload: Record<string, string | number | boolean | Record<string, number>> = {},
    count?: number,
): Promise<void> {
    return guarded(Promise.resolve(), () => {
        if (!instrumented(job) || !Object.values(RECORD).includes(name)) return Promise.resolve();
        const record: Record<string, unknown> = { ...payload, obj_name: name };
        if (count !== undefined) {
            if (!isInteger(count) || count < 0) return Promise.resolve();
            record.count = count;
        }
        delete record.client_id;
        return job.logger.log(EventScope.debugInfo, record).then(() => undefined, (error: unknown) => {
            if (!switchedOff()) recordFailure(error);
        });
    });
}
