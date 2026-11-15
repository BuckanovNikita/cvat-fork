// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The event contract between the UI logging and the Team Analytics SQL (cvat/apps/team_analytics/sql/).
// Field and record names here are read by the service's SQL: change both together.
// No new event type exists (ADR 0002): fields ride on stock events, records are `debug:info` events.

// Payload fields added to the stock draw, paste, propagate, drag, resize and delete events.
export const PAYLOAD = {
    // one of SHAPE_TYPES, or MIXED when the action touched several kinds
    shapeType: 'shape_type',
    // number of single-frame rectangles (bounding boxes) among the objects; 0 allowed
    rectangleCount: 'rectangle_count',
    // 'shape' (single-frame) or 'track'; MIXED when the action touched both
    objectType: 'object_type',
    // 'hotkey' or 'mouse' (supplied by input-method.ts)
    inputMethod: 'input_method',
    // drag and resize only: the object's client-side id within the job for this browser session.
    // Never `client_id`: the logger writes the browser's id under that key.
    objectRef: 'object_ref',
    // drag and resize only: frame number
    frame: 'frame',
    // drag only: GROUP.move on the group event, GROUP.grabbed on CVAT's own drag of the grabbed object
    group: 'group',
} as const;

// A group move (several selected objects dragged together, or the selection box moved) is one
// `drag:object` event for the gesture, sent by Team Analytics:
//   duration   the gesture's duration, from the canvas
//   count      the number of objects moved (the event's count column)
//   payload    `group` = GROUP.move, the shape fields of all objects moved (`rectangle_count` = how many
//              of them are bounding boxes), `frame`, `input_method` 'mouse'; no `object_ref`, no `obj_id`
// It counts one alignment per object moved, sharing the duration equally; it ends the alignment runs
// before it, and no later drag continues it. When the gesture began by dragging one object, CVAT still
// logs its own `drag:object` of that object right after; that event carries `group` = GROUP.grabbed and
// is no operation of its own.
export const GROUP = {
    move: 'move',
    grabbed: 'grabbed',
} as const;

// `obj_name` of the `debug:info` records Team Analytics adds (logged through the job logger).
export const RECORD = {
    classChange: 'team_analytics:class_change',
    modelCreation: 'team_analytics:model_creation',
    inputSummary: 'team_analytics:input_summary',
} as const;

export type RecordName = typeof RECORD[keyof typeof RECORD];

export const SHAPE_TYPES = [
    'rectangle', 'polygon', 'polyline', 'points', 'ellipse', 'cuboid', 'mask', 'skeleton',
] as const;

export const MIXED = 'mixed';

// A tag is an object without a shape. It has no value in the contract's lists, so a tag is described
// with shape type and object type 'tag' (never a bounding box). The SQL counts it under All shapes.
export const TAG = 'tag';

export const INPUT_METHODS = ['hotkey', 'mouse'] as const;
export type InputMethod = typeof INPUT_METHODS[number];
