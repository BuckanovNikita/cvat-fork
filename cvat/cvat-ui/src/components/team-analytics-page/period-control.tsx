// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';

import {
    Address, PERIODS, PeriodKey, shiftMonth,
} from './address';
import { HistoryStatus, Period } from './service';
import { dayLabel, monthLabel } from './format';
import { NOT_PROCESSED, monthAvailable, periodAvailable } from './history';

// How the cards name the selected period.
export function periodLabel(address: Address, latestMonth: string): string {
    switch (address.period) {
        case 'two_weeks': return 'Last 14 days';
        case 'year': return 'Last 12 months';
        case 'month': return address.month ?
            `${monthLabel(address.month)}${address.month === latestMonth ? ' · to date' : ''}` : 'Month';
        default: return 'Last 7 days';
    }
}

interface Props {
    address: Address;
    // the viewer's current month, YYYY-MM: the latest month that can be chosen
    latestMonth: string;
    // the days the shown figures cover, when known
    period?: Period;
    // how far history is processed: periods and months not wholly processed are not offered
    history?: HistoryStatus | null;
    onChange(change: Partial<Address>): void;
}

// Week, Two weeks, Month (stepping through earlier months) and Year. There is no custom range.
export default function PeriodControl({
    address, latestMonth, period, history, onChange,
}: Props): JSX.Element {
    const isMonth = address.period === 'month' && !!address.month;
    const previousAvailable = !isMonth || monthAvailable(history, shiftMonth(address.month as string, -1));
    let range = '';
    if (isMonth) {
        range = periodLabel(address, latestMonth);
    } else if (period && period.name === address.period) {
        const sameYear = period.first_day.slice(0, 4) === period.last_day.slice(0, 4);
        range = `${dayLabel(period.first_day, !sameYear)} – ${dayLabel(period.last_day, true)}`;
    }
    return (
        <div className='cvat-team-analytics-period-control'>
            <div className='cvat-team-analytics-periods' role='group' aria-label='Period'>
                {PERIODS.map(({ key, label }) => {
                    const available = periodAvailable(history, key);
                    return (
                        <button
                            key={key}
                            type='button'
                            className='cvat-team-analytics-period'
                            aria-pressed={address.period === key}
                            disabled={!available}
                            title={available ? undefined : NOT_PROCESSED}
                            onClick={() => onChange({ period: key as PeriodKey, month: null })}
                        >
                            {label}
                        </button>
                    );
                })}
            </div>
            <div className='cvat-team-analytics-range'>
                {isMonth ? (
                    <button
                        type='button'
                        className='cvat-team-analytics-step'
                        aria-label='Previous month'
                        title={previousAvailable ? 'Previous month' : NOT_PROCESSED}
                        disabled={!previousAvailable}
                        onClick={() => onChange({ month: shiftMonth(address.month as string, -1) })}
                    >
                        <LeftOutlined />
                    </button>
                ) : null}
                <span className='cvat-team-analytics-range-label'>{range}</span>
                {isMonth ? (
                    <button
                        type='button'
                        className='cvat-team-analytics-step'
                        aria-label='Next month'
                        title='Next month'
                        disabled={(address.month as string) >= latestMonth}
                        onClick={() => onChange({ month: shiftMonth(address.month as string, 1) })}
                    >
                        <RightOutlined />
                    </button>
                ) : null}
            </div>
        </div>
    );
}
