// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The Bounding boxes / All shapes switch: kept in the page address (`shapes=all`; Bounding boxes, the
// default, is not written), sent to the service as `shapes`, and named in every operation card after the
// shapes the service says the figures cover (a legacy period always covers all shapes).

import { OperationsFigures } from './service';

export type Shapes = 'bounding_boxes' | 'all';

export const DEFAULT_SHAPES: Shapes = 'bounding_boxes';

export const SHAPE_OPTIONS: { key: Shapes; label: string }[] = [
    { key: 'bounding_boxes', label: 'Bounding boxes' },
    { key: 'all', label: 'All shapes' },
];

export function readShapes(search: string): Shapes {
    return new URLSearchParams(search).get('shapes') === 'all' ? 'all' : DEFAULT_SHAPES;
}

// The query string for `shapes`, keeping every other key of `search`.
export function shapesSearch(shapes: Shapes | undefined, search: string): string {
    const query = new URLSearchParams(search);
    if (shapes === 'all') query.set('shapes', 'all');
    else query.delete('shapes');
    const text = query.toString();
    return text ? `?${text}` : '';
}

export interface ShapeWording {
    // 'Bounding boxes' or 'All shapes'
    label: string;
    // the thing counted: 'box' / 'object'
    noun: string;
    // plural, capitalized: 'Boxes' / 'Objects'
    nouns: string;
    // the operations table title
    operations: string;
}

// How the cards name the shapes the figures cover (all shapes when the response does not say).
export function shapeWording(figures: Pick<OperationsFigures, 'shapes'>): ShapeWording {
    if (figures.shapes === 'bounding_boxes') {
        return {
            label: 'Bounding boxes', noun: 'box', nouns: 'Boxes', operations: 'Bounding box operations',
        };
    }
    return {
        label: 'All shapes', noun: 'object', nouns: 'Objects', operations: 'Object operations',
    };
}
