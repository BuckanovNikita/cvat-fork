// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { TimeSeries } from '../service';
import { dayLabel, exactHours } from '../format';
import { FullViewButton } from '../full-view-button';
import { Term } from '../definitions';

interface Props {
    series: TimeSeries;
    // opens the chart's full view
    onFullView?: () => void;
    // the chart alone in its full view: taller, values on more bars
    large?: boolean;
}

const HOUR_MS = 3600000;
// Up to this many bars each shows its value; more bars keep it in the hover text only.
const MAX_CAPTIONED_BARS = 14;
// the same in the full view
const MAX_CAPTIONED_BARS_LARGE = 31;
// About this many axis labels at most, counted back from the last bar (today).
const MAX_AXIS_LABELS = 7;

// The smallest of 1, 2, 2.5, 5 times a power of ten that is at least `max`.
function scaleTop(max: number): number {
    if (max <= 0) return 1;
    const power = 10 ** Math.floor(Math.log10(max));
    return [1, 2, 2.5, 5, 10].map((step) => step * power).find((top) => top >= max) as number;
}

// Working time per day of the period, or per week for Year. Bars are plain divs in the style of
// the task progress widget.
function WorkingTimeOverPeriodCard({ series, onFullView, large = false }: Props): JSX.Element {
    const weekly = series.unit === 'week';
    const { buckets } = series;
    const hours = buckets.map((bucket) => bucket.working_time_ms / HOUR_MS);
    const top = scaleTop(Math.max(0, ...hours));
    const captioned = buckets.length <= (large ? MAX_CAPTIONED_BARS_LARGE : MAX_CAPTIONED_BARS);
    const labelEvery = Math.max(1, Math.ceil(buckets.length / MAX_AXIS_LABELS));
    const last = buckets.length - 1;

    return (
        <section
            className={`cvat-team-analytics-card cvat-team-analytics-time-chart${
                large ? ' cvat-team-analytics-time-chart-large' : ''}`}
        >
            {large ? null : (
                <div className='cvat-team-analytics-card-header'>
                    <Text strong>
                        {/* the full view shows the chart without the definitions */}
                        {large ? 'Working time' : <Term name='Working time'>Working time</Term>}
                        {weekly ? ' by week' : ' by day'}
                    </Text>
                    <Text type='secondary'>Hours as the server counts working time</Text>
                    <FullViewButton onClick={onFullView} />
                </div>
            )}
            <div className='cvat-team-analytics-time-plot'>
                <div className='cvat-team-analytics-time-scale' aria-hidden>
                    {[top, top / 2, 0].map((tick) => (
                        <span key={tick}>{`${tick.toLocaleString('en-US')} h`}</span>
                    ))}
                </div>
                <div className='cvat-team-analytics-time-bars'>
                    {buckets.map((bucket, index) => (
                        <div
                            key={bucket.start}
                            className='cvat-team-analytics-time-bar'
                            title={`${weekly ? 'Week of ' : ''}${dayLabel(bucket.start)}: ${exactHours(bucket.working_time_ms)}`}
                        >
                            <span className='cvat-team-analytics-time-value'>
                                {captioned ? hours[index].toFixed(1) : ''}
                            </span>
                            <div className='cvat-team-analytics-time-track'>
                                <div
                                    className='cvat-team-analytics-time-fill'
                                    style={{ height: `${(hours[index] / top) * 100}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
            <div className='cvat-team-analytics-time-axis'>
                {buckets.map((bucket, index) => (
                    <div key={bucket.start}>
                        {(last - index) % labelEvery === 0 ? (
                            <span className='cvat-team-analytics-time-label'>{dayLabel(bucket.start)}</span>
                        ) : null}
                    </div>
                ))}
            </div>
        </section>
    );
}

export default React.memo(WorkingTimeOverPeriodCard);
