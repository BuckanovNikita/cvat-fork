// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Processed history: the progress bar while history is processed, which periods may be offered, the
// notice shown instead of a period's figures until all of it is processed, and the notice that stands
// in for trends until three complete weeks are ready. A status that is not known disables nothing.

import React from 'react';

import { HistoryStatus } from './service';
import { dayLabel } from './format';

export const NOT_PROCESSED = 'Not processed yet';

// Whether period `key` (a period of address.ts) is wholly processed.
export function periodAvailable(history: HistoryStatus | null | undefined, key: string): boolean {
    if (!history || history.complete) return true;
    return !!history.periods[key];
}

// Whether calendar month `month` (YYYY-MM) is wholly processed.
export function monthAvailable(history: HistoryStatus | null | undefined, month: string): boolean {
    if (!history || history.complete) return true;
    // YYYY-MM strings compare in calendar order
    return !!history.earliest_month && month >= history.earliest_month;
}

export function HistoryProgress({ history }: { history?: HistoryStatus | null }): JSX.Element | null {
    if (!history || history.complete) return null;
    const { days_ready: daysReady, days_total: daysTotal, ready_from_day: readyFromDay } = history;
    // Only an administrator's status has the day counts; everyone else's has the percentage alone.
    const counted = typeof daysReady === 'number' && typeof daysTotal === 'number';
    const percent = history.percent ?? 0;
    const ready = readyFromDay ? `Ready from ${dayLabel(readyFromDay, true)}` : 'Nothing ready yet';
    return (
        <div className='cvat-team-analytics-history'>
            <div className='cvat-team-analytics-history-head'>
                <span className='cvat-team-analytics-history-title'>Processing history</span>
                {counted && <span>{`${ready} · ${daysReady} of ${daysTotal} days`}</span>}
                <span className='cvat-team-analytics-history-percent'>{`${percent}%`}</span>
            </div>
            <div
                className='cvat-team-analytics-history-bar'
                role='progressbar'
                aria-label='History processed'
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
            >
                <div className='cvat-team-analytics-history-fill' style={{ width: `${percent}%` }} />
            </div>
            <div className='cvat-team-analytics-history-note'>
                Recent days are processed first. Two weeks, earlier months and the year become selectable as
                processing reaches them; the page never shows a period that is only partly processed.
            </div>
        </div>
    );
}

// Shown instead of the figures of a period that is not wholly processed.
export function NotProcessedNotice(): JSX.Element {
    return (
        <div className='cvat-team-analytics-not-processed' role='status'>
            <div className='cvat-team-analytics-notice-title'>This period is not processed yet</div>
            <div>
                Its figures appear once every day of it is processed, so a partial total is never shown.
                Pick a shorter period meanwhile.
            </div>
        </div>
    );
}

const COUNTS = ['None are', 'One is', 'Two are'];

// Trends need three complete weeks of processed history; until then this notice stands in for them.
// The trends card renders as `children` and appears once they are ready.
export function TrendsGate({ history, children = null }: {
    history?: HistoryStatus | null;
    children?: React.ReactNode;
}): JSX.Element | null {
    if (!history || history.trends_ready) return children ? <>{children}</> : null;
    const ready = COUNTS[Math.min(history.complete_weeks, 2)];
    return (
        <div className='cvat-team-analytics-card cvat-team-analytics-trends-pending'>
            <div className='cvat-team-analytics-notice-title'>Trends appear as history is processed</div>
            <div>{`A trend needs at least three complete weeks. ${ready} ready so far.`}</div>
        </div>
    );
}
