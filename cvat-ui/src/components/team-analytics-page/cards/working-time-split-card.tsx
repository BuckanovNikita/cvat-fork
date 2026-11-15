// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { OperationsFigures } from '../service';
import { formatHours, formatShare } from '../format';
import { OPERATION_LOOKS, hasNoJobWork, isRecorded } from '../operations';
import { shapeWording } from '../shapes';
import { FullViewButton } from '../full-view-button';

interface Props {
    figures: OperationsFigures;
    onFullView?: () => void;
}

const HOUR_MS = 3600000;
// a part this large or larger carries its share inside the bar
const SHARE_INSIDE_FROM = 0.09;

// Where working time goes: one stacked bar of the operations and Other, with its legend (name,
// time, share) inside the card so every share reads without hovering.
function WorkingTimeSplitCard({ figures, onFullView }: Props): JSX.Element {
    const header = (
        <div className='cvat-team-analytics-card-header'>
            <Text strong>Where working time goes</Text>
            <FullViewButton onClick={onFullView} />
        </div>
    );
    if (hasNoJobWork(figures)) {
        return (
            <section className='cvat-team-analytics-card cvat-team-analytics-split'>
                {header}
                <Text type='secondary' className='cvat-team-analytics-empty'>No job work in this period</Text>
            </section>
        );
    }

    const parts = figures.rows.filter((row) => isRecorded(figures, row.operation)).map((row) => {
        const look = OPERATION_LOOKS[row.operation];
        return {
            key: row.operation,
            look,
            time: formatHours(row.time_ms),
            share: formatShare(row.share),
            grow: row.time_ms / HOUR_MS,
            inside: row.share !== null && row.share >= SHARE_INSIDE_FROM ? formatShare(row.share) : '',
        };
    });
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-split'>
            {header}
            <Text type='secondary'>
                {`${shapeWording(figures).label} · ${formatHours(figures.active_time_ms)} of working time`}
            </Text>
            <div className='cvat-team-analytics-split-bar'>
                {parts.map((part) => (
                    <div
                        key={part.key}
                        className='cvat-team-analytics-split-part'
                        title={`${part.look.name}: ${part.time} (${part.share})`}
                        style={{ flex: `${part.grow} 1 0`, background: part.look.color, color: part.look.ink }}
                    >
                        {part.inside}
                    </div>
                ))}
            </div>
            <ul className='cvat-team-analytics-split-legend'>
                {parts.map((part) => (
                    <li key={part.key} className='cvat-team-analytics-split-legend-item'>
                        <span className='cvat-team-analytics-swatch' style={{ background: part.look.color }} />
                        <span className='cvat-team-analytics-split-legend-name'>{part.look.name}</span>
                        <span className='cvat-team-analytics-value'>{part.time}</span>
                        <span className='cvat-team-analytics-value cvat-team-analytics-split-legend-share'>{part.share}</span>
                    </li>
                ))}
            </ul>
        </section>
    );
}

export default React.memo(WorkingTimeSplitCard);
