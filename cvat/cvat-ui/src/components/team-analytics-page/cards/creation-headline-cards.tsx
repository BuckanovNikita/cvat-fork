// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { OperationsFigures } from '../service';
import { formatCount, formatSeconds, shortCount } from '../format';
import { operationRow } from '../operations';
import { shapeWording } from '../shapes';

interface Props {
    figures: OperationsFigures;
}

// Headline figures for the scope: objects created and the average time to create one.
function CreationHeadlineCards({ figures }: Props): JSX.Element {
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
                <Text type='secondary'>by annotators</Text>
            </section>
            <section className='cvat-team-analytics-card cvat-team-analytics-average-creation'>
                <Text type='secondary'>{`Avg time per ${noun}`}</Text>
                <div className='cvat-team-analytics-headline-value'>{formatSeconds(creation?.average_ms ?? null)}</div>
                <Text type='secondary'>to create one</Text>
            </section>
        </>
    );
}

export default React.memo(CreationHeadlineCards);
