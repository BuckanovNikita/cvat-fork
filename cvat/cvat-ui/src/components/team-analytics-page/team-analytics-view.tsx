// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';
import Spin from 'antd/lib/spin';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';

import { PageState, Status } from './service';
import { Address, currentMonth } from './address';
import TeamAnalyticsErrorPanel from './error-panel';
import PeriodControl, { periodLabel } from './period-control';
import { FreshnessStamp, StaleWarning } from './freshness';
import WorkingTimeByAnnotatorCard from './cards/working-time-by-annotator-card';
import WorkingTimeOverPeriodCard from './cards/working-time-over-period-card';

interface Props {
    // slug of the organization selected in CVAT, null for none
    organization: string | null;
    state: PageState;
    onBackToTasks?: () => void;
    // the selection kept in the page address; without it there is no filter row
    address?: Address;
    onAddressChange?: (change: Partial<Address>) => void;
    // the viewer's current month (YYYY-MM)
    currentMonth?: string;
    // figures for a new selection are loading: the shown ones are kept, dimmed
    pending?: boolean;
    status?: Status | null;
    timeZone?: string;
}

const WEEK: Address = { period: 'week', month: null };

function scopeLabel(organization: string | null, state: PageState): string {
    if (organization) return `Organization ${organization}`;
    // without an organization only an administrator reads instance scope
    if (state.kind === 'select-organization') return 'No organization selected';
    return 'All organizations and personal workspaces';
}

// Presentational: renders one page state. Data loading lives in team-analytics-page.tsx.
export default function TeamAnalyticsView({
    organization, state, onBackToTasks, address, onAddressChange, pending = false, status = null,
    timeZone = 'UTC', currentMonth: latestMonth = currentMonth(),
}: Props): JSX.Element {
    if (state.kind === 'denied') {
        return (
            <div className='cvat-team-analytics-page'>
                <Result
                    className='cvat-team-analytics-denied'
                    status='403'
                    title='Team analytics is not available'
                    subTitle={'This page is for administrators and for owners and maintainers of the current ' +
                        'organization. The analytics service checks the same roles before it returns any data, ' +
                        'so a direct link shows nothing more.'}
                    extra={(
                        <a
                            className='cvat-team-analytics-back'
                            href='/tasks'
                            onClick={(event: React.MouseEvent): void => {
                                if (onBackToTasks) {
                                    event.preventDefault();
                                    onBackToTasks();
                                }
                            }}
                        >
                            Back to tasks
                        </a>
                    )}
                />
            </div>
        );
    }

    let content: JSX.Element;
    if (state.kind === 'loading') {
        content = <Spin className='cvat-team-analytics-loading' size='large' />;
    } else if (state.kind === 'error') {
        content = <TeamAnalyticsErrorPanel />;
    } else if (state.kind === 'signed-out') {
        content = (
            <Result
                className='cvat-team-analytics-signed-out'
                status='info'
                title='Your session has ended'
                subTitle='Sign in again to see team analytics.'
            />
        );
    } else if (state.kind === 'select-organization') {
        content = (
            <Result
                className='cvat-team-analytics-select-organization'
                status='info'
                title='Select an organization'
                subTitle='Team analytics shows one organization at a time. Choose it in the organization menu at the top right.'
            />
        );
    } else {
        content = (
            <div
                className={`cvat-team-analytics-cards${pending ? ' cvat-team-analytics-pending' : ''}`}
                aria-busy={pending}
            >
                {state.overview.time_series ? <WorkingTimeOverPeriodCard series={state.overview.time_series} /> : null}
                <WorkingTimeByAnnotatorCard
                    rows={state.overview.by_annotator.rows}
                    periodLabel={periodLabel(address ?? WEEK, latestMonth)}
                />
            </div>
        );
    }

    const showFilters = !!address && !!onAddressChange && ['ready', 'loading', 'error'].includes(state.kind);
    const refresh = state.kind === 'ready' ? status?.refresh : undefined;
    return (
        <div className='cvat-team-analytics-page'>
            <div className='cvat-team-analytics-header'>
                <Title level={4}>Team analytics</Title>
                <Text type='secondary'>
                    {scopeLabel(organization, state)}
                    {' · annotation work inside jobs'}
                </Text>
            </div>
            {showFilters ? (
                <div className='cvat-team-analytics-filters'>
                    <PeriodControl
                        address={address as Address}
                        latestMonth={latestMonth}
                        period={state.kind === 'ready' ? state.overview.period : undefined}
                        onChange={onAddressChange as (change: Partial<Address>) => void}
                    />
                    {refresh ? <FreshnessStamp refresh={refresh} timeZone={timeZone} /> : null}
                </div>
            ) : null}
            {refresh ? <StaleWarning refresh={refresh} timeZone={timeZone} /> : null}
            {content}
        </div>
    );
}
