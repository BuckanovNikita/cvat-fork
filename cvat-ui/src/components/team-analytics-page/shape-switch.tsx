// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { SHAPE_OPTIONS, Shapes } from './shapes';

interface Props {
    shapes: Shapes;
    onChange(shapes: Shapes): void;
}

// Bounding boxes or All shapes, for every operation figure on the page.
export default function ShapeSwitch({ shapes, onChange }: Props): JSX.Element {
    return (
        <div className='cvat-team-analytics-shapes' role='group' aria-label='Shapes'>
            {SHAPE_OPTIONS.map(({ key, label }) => (
                <button
                    key={key}
                    type='button'
                    className='cvat-team-analytics-shape'
                    aria-pressed={shapes === key}
                    onClick={() => onChange(key)}
                >
                    {label}
                </button>
            ))}
        </div>
    );
}
