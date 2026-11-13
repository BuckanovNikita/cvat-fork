// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { AnnotatorWorkingTime } from '../service';
import { exactHours, formatHours } from '../format';

interface Props {
    rows: AnnotatorWorkingTime[];
}

// Working time per annotator, in the order the service gives (largest first). Bars are plain
// divs in the style of the task progress widget.
function WorkingTimeByAnnotatorCard({ rows }: Props): JSX.Element {
    const largest = rows.reduce((max, row) => Math.max(max, row.working_time_ms), 0);
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-working-time-by-annotator'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>Working time by annotator</Text>
                <Text type='secondary'>Last 7 days</Text>
            </div>
            {rows.length === 0 ? (
                <Text type='secondary' className='cvat-team-analytics-empty'>No job work in this period</Text>
            ) : rows.map((row) => (
                <div
                    key={row.user_id}
                    className='cvat-team-analytics-annotator-row'
                    title={`${row.user_name}: ${exactHours(row.working_time_ms)}`}
                >
                    <span className='cvat-team-analytics-name' title={row.user_name}>{row.user_name}</span>
                    <span className='cvat-team-analytics-value'>{formatHours(row.working_time_ms)}</span>
                    <div className='cvat-team-analytics-bar'>
                        <div
                            className='cvat-team-analytics-bar-fill'
                            style={{ width: `${largest > 0 ? (row.working_time_ms / largest) * 100 : 0}%` }}
                        />
                    </div>
                </div>
            ))}
        </section>
    );
}

export default React.memo(WorkingTimeByAnnotatorCard);
