// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { Rest } from '../service';
import { exactHours, formatHours } from '../format';
import { FullViewButton, ShowAllButton } from '../full-view-button';

export interface BreakdownRow {
    id: number;
    name: string;
    working_time_ms: number;
}

interface Props {
    // `annotator` or `project`: names the card and row classes
    kind: string;
    title: string;
    subtitle: string;
    rows: BreakdownRow[];
    rest?: Rest;
    // the row set as the page's filter, if any
    selected?: number | null;
    // clicking a row sets it as the filter, clicking the selected row again removes it
    onPick?: (id: number) => void;
    // opens the chart's full view with every row
    onFullView?: () => void;
}

// Working time per annotator or project, in the order the service gives (largest first), with the
// rows not shown as one line. Bars are plain divs in the style of the task progress widget; the
// legend sits inside the card.
export default function WorkingTimeBreakdown({
    kind, title, subtitle, rows, rest, selected = null, onPick, onFullView,
}: Props): JSX.Element {
    const largest = rows.reduce((max, row) => Math.max(max, row.working_time_ms), 0);
    return (
        <section className={`cvat-team-analytics-card cvat-team-analytics-working-time-by-${kind}`}>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>{title}</Text>
                <Text type='secondary'>{subtitle}</Text>
                <FullViewButton onClick={onFullView} />
            </div>
            <div className='cvat-team-analytics-legend'>
                <span className='cvat-team-analytics-legend-item'>
                    <span className='cvat-team-analytics-legend-swatch cvat-team-analytics-working-time-swatch' />
                    Working time
                </span>
                {onPick ? <Text type='secondary'>Select a row to filter the whole page</Text> : null}
            </div>
            {rows.length === 0 ? (
                <Text type='secondary' className='cvat-team-analytics-empty'>No job work in this period</Text>
            ) : rows.map((row) => (
                <button
                    type='button'
                    key={row.id}
                    className={`cvat-team-analytics-${kind}-row cvat-team-analytics-breakdown-row${
                        row.id === selected ? ' cvat-team-analytics-selected' : ''}`}
                    aria-pressed={row.id === selected}
                    title={`${row.name}: ${exactHours(row.working_time_ms)}`}
                    onClick={onPick ? () => onPick(row.id) : undefined}
                >
                    <span className='cvat-team-analytics-name' title={row.name}>{row.name}</span>
                    <span className='cvat-team-analytics-value'>{formatHours(row.working_time_ms)}</span>
                    <span className='cvat-team-analytics-bar'>
                        <span
                            className='cvat-team-analytics-bar-fill'
                            style={{ width: `${largest > 0 ? (row.working_time_ms / largest) * 100 : 0}%` }}
                        />
                    </span>
                </button>
            ))}
            {rest && rest.count > 0 ? (
                <div className='cvat-team-analytics-rest' title={exactHours(rest.working_time_ms)}>
                    <span>{`${rest.count.toLocaleString('en-US')} more, not shown`}</span>
                    <span className='cvat-team-analytics-value'>{formatHours(rest.working_time_ms)}</span>
                </div>
            ) : null}
            {rest && rest.count > 0 ? <ShowAllButton count={rows.length + rest.count} onClick={onFullView} /> : null}
        </section>
    );
}
