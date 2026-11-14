// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import { ClockCircleOutlined, WarningOutlined } from '@ant-design/icons';

import { Status } from './service';

type Refresh = NonNullable<Status['refresh']>;

function dayIn(moment: Date, timeZone: string): string {
    return moment.toLocaleDateString('en-CA', { timeZone });
}

// '17:40', or 'Nov 12, 17:40' when it was not on the service's today, in the viewer's zone.
export function refreshTime(at: string, now: string, timeZone: string): string {
    const moment = new Date(at);
    const time = moment.toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', hour12: false, timeZone,
    });
    if (dayIn(moment, timeZone) === dayIn(new Date(now), timeZone)) return time;
    return `${moment.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone })}, ${time}`;
}

// `status` as it stands `elapsedMs` after it was read: the service's clock moved on by that much,
// so the last refresh may have become too old. Used when a newer status cannot be read.
export function agedStatus(status: Status, elapsedMs: number): Status {
    const { refresh } = status;
    if (!refresh) return status;
    const now = new Date(Date.parse(refresh.now) + elapsedMs);
    const age = refresh.last_success_at ? now.getTime() - Date.parse(refresh.last_success_at) : Infinity;
    return {
        ...status,
        refresh: { ...refresh, now: now.toISOString(), stale: refresh.stale || age > refresh.stale_after_s * 1000 },
    };
}

interface Props {
    refresh: Refresh;
    timeZone: string;
}

// "Data as of" stamp for the filter row.
export function FreshnessStamp({ refresh, timeZone }: Props): JSX.Element {
    const minutes = Math.round(refresh.interval_s / 60);
    return (
        <span className='cvat-team-analytics-freshness'>
            <ClockCircleOutlined />
            {refresh.last_success_at ?
                `Data as of ${refreshTime(refresh.last_success_at, refresh.now, timeZone)}` +
                ` · refreshed every ${minutes} min` :
                'Not refreshed yet'}
        </span>
    );
}

// Shown under the filter row when the figures are too old (the service decides, by its own clock).
export function StaleWarning({ refresh, timeZone }: Props): JSX.Element | null {
    if (!refresh.stale) return null;
    const limit = Math.round(refresh.stale_after_s / 60);
    return (
        <div className='cvat-team-analytics-stale' role='alert'>
            <WarningOutlined />
            <span>
                {refresh.last_success_at ?
                    'The figures were last refreshed at ' +
                    `${refreshTime(refresh.last_success_at, refresh.now, timeZone)}, ` +
                    `more than ${limit} minutes ago. Recent work may be missing.` :
                    'The figures have not been refreshed yet. Recent work may be missing.'}
            </span>
        </div>
    );
}
