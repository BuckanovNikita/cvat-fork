// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { CreationMethods, OperationsFigures } from '../service';
import { formatCount, formatSeconds, shortCount } from '../format';
import { METHOD_NAMES } from '../creation-methods';
import { operationRow } from '../operations';
import { shapeWording } from '../shapes';
import { Term } from '../definitions';

interface Props {
    figures: OperationsFigures;
    methods?: CreationMethods;
}

// 'drawn 6.2 s · pasted 1.5 s · propagated 0.8 s'
function perMethod(methods: CreationMethods): string {
    return methods.rows
        .map((row) => `${METHOD_NAMES[row.method].toLowerCase()} ${formatSeconds(row.average_ms)}`)
        .join(' · ');
}

// Headline figures for the scope: objects created and the average time to create one, with the
// average of each creation method beneath it when the response has them. Model objects are shown beside
// the objects created, never inside them.
function CreationHeadlineCards({ figures, methods }: Props): JSX.Element {
    const creation = operationRow(figures, 'creation');
    const objects = creation?.objects ?? 0;
    const { noun, nouns } = shapeWording(figures);
    return (
        <>
            <section
                className='cvat-team-analytics-card cvat-team-analytics-objects-created'
                title={`${formatCount(objects)} exactly`}
            >
                <Text type='secondary'>{`${nouns} created`}</Text>
                <div className='cvat-team-analytics-headline-value'>{shortCount(objects)}</div>
                <Text type='secondary'>
                    {methods?.model ? `by annotators · plus ${shortCount(methods.model.objects)} by model` : 'by annotators'}
                </Text>
            </section>
            <section className='cvat-team-analytics-card cvat-team-analytics-average-creation'>
                <Text type='secondary'><Term name='Time per operation'>{`Avg time per ${noun}`}</Term></Text>
                <div className='cvat-team-analytics-headline-value'>{formatSeconds(creation?.average_ms ?? null)}</div>
                <Text type='secondary'>{methods ? perMethod(methods) : 'to create one'}</Text>
            </section>
        </>
    );
}

export default React.memo(CreationHeadlineCards);
