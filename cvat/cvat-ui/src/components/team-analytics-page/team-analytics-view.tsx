// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';
import Spin from 'antd/lib/spin';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';

import {
    Overview, PageState, Period, ProjectNames, Status,
} from './service';
import { Address, currentMonth } from './address';
import { Filters } from './filters';
import { projectName } from './format';
import TeamAnalyticsErrorPanel from './error-panel';
import PeriodControl, { periodLabel } from './period-control';
import { FreshnessStamp, StaleWarning } from './freshness';
import { HistoryProgress, NotProcessedNotice, TrendsGate } from './history';
import FilterChips from './filter-chips';
import WorkingTimeByAnnotatorCard from './cards/working-time-by-annotator-card';
import WorkingTimeByProjectCard from './cards/working-time-by-project-card';
import WorkingTimeOverPeriodCard from './cards/working-time-over-period-card';
import AnnotatorsCard from './cards/annotators-card';
import SessionsCard from './cards/sessions-card';
import CreationHeadlineCards from './cards/creation-headline-cards';
import WorkingTimeSplitCard from './cards/working-time-split-card';
import OperationsTableCard from './cards/operations-table-card';
import LegacyNotice from './legacy-notice';
import ShapeSwitch from './shape-switch';
import { DEFAULT_SHAPES } from './shapes';

interface Props {
    // slug of the organization selected in CVAT, null for none
    organization: string | null;
    state: PageState;
    onBackToTasks?: () => void;
    // the selection kept in the page address (period and filters); without it there is no filter row
    // and rows are not clickable
    address?: Address;
    onAddressChange?: (change: Partial<Address>) => void;
    // the viewer's current month (YYYY-MM)
    currentMonth?: string;
    // figures for a new selection are loading: the shown ones are kept, dimmed
    pending?: boolean;
    status?: Status | null;
    timeZone?: string;
    // names of the shown projects as CVAT returns them to the viewer
    projectNames?: ProjectNames;
}

const WEEK: Address = {
    period: 'week', month: null, project: null, annotator: null, shapes: DEFAULT_SHAPES,
};

// The selection the shown figures cover: the period the service echoed, which differs from the
// address while figures for a new selection load.
function shownAddress(period: Period | undefined, address: Address | undefined): Address {
    if (period) return { ...(address ?? WEEK), period: period.name as Address['period'], month: period.month };
    return address ?? WEEK;
}

function annotatorLabel(id: number | null, overview: Overview | null): string {
    if (id === null) return '';
    const shown = overview?.by_annotator.rows.find((row) => row.user_id === id)?.user_name;
    const echoed = overview?.filters?.annotator?.user_id === id ? overview.filters.annotator.user_name : null;
    return shown ?? echoed ?? `Annotator #${id}`;
}

function scopeLabel(organization: string | null, state: PageState): string {
    if (organization) return `Organization ${organization}`;
    // without an organization only an administrator reads instance scope
    if (state.kind === 'select-organization') return 'No organization selected';
    return 'All organizations and personal workspaces';
}

// Presentational: renders one page state. Data loading lives in team-analytics-page.tsx.
export default function TeamAnalyticsView({
    organization, state, onBackToTasks, address, onAddressChange, pending = false, status = null,
    timeZone = 'UTC', currentMonth: latestMonth = currentMonth(), projectNames = {},
}: Props): JSX.Element {
    const filters: Filters = { project: address?.project ?? null, annotator: address?.annotator ?? null };
    // clicking a row sets it as the filter; clicking the selected row again removes it
    const pick = (key: keyof Filters) => (onAddressChange ? (id: number): void => {
        onAddressChange({ [key]: filters[key] === id ? null : id });
    } : undefined);

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
    } else if (state.overview.processed === false) {
        // partial figures are never shown: one gate for every card
        content = <NotProcessedNotice />;
    } else {
        const { overview } = state;
        const annotatorRest = overview.by_annotator.rest?.count ?? 0;
        const shownPeriod = periodLabel(shownAddress(overview.period, address), latestMonth);
        content = (
            <div
                className={`cvat-team-analytics-cards${pending ? ' cvat-team-analytics-pending' : ''}`}
                aria-busy={pending}
            >
                {overview.operations?.legacy ? <LegacyNotice /> : null}
                {overview.headline ? (
                    <AnnotatorsCard
                        annotators={overview.headline.annotators}
                        projects={overview.headline.projects}
                        of={filters.annotator === null ? null : overview.by_annotator.rows.length + annotatorRest}
                        projectSelected={filters.project !== null}
                    />
                ) : null}
                {overview.sessions ? <SessionsCard figures={overview.sessions} /> : null}
                {overview.operations ? <CreationHeadlineCards figures={overview.operations} /> : null}
                {overview.time_series ? <WorkingTimeOverPeriodCard series={overview.time_series} /> : null}
                {overview.operations ? <WorkingTimeSplitCard figures={overview.operations} /> : null}
                {overview.operations ? <OperationsTableCard figures={overview.operations} /> : null}
                {overview.by_project ? (
                    <WorkingTimeByProjectCard
                        rows={overview.by_project.rows}
                        rest={overview.by_project.rest}
                        names={projectNames}
                        selected={filters.project}
                        onPick={pick('project')}
                        periodLabel={shownPeriod}
                    />
                ) : null}
                <WorkingTimeByAnnotatorCard
                    rows={overview.by_annotator.rows}
                    rest={overview.by_annotator.rest}
                    selected={filters.annotator}
                    onPick={pick('annotator')}
                    periodLabel={shownPeriod}
                />
                <TrendsGate history={status?.history} />
            </div>
        );
    }

    const showFilters = !!address && !!onAddressChange && ['ready', 'loading', 'error'].includes(state.kind);
    const refresh = state.kind === 'ready' ? status?.refresh : undefined;
    const history = state.kind === 'ready' ? status?.history : undefined;
    const shownOverview = state.kind === 'ready' ? state.overview : null;
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
                        history={history}
                        onChange={onAddressChange as (change: Partial<Address>) => void}
                    />
                    {/* a legacy period has all shapes only: no switch */}
                    {shownOverview?.operations?.legacy ? null : (
                        <ShapeSwitch
                            shapes={(address as Address).shapes ?? DEFAULT_SHAPES}
                            onChange={(shapes) => (onAddressChange as (change: Partial<Address>) => void)({ shapes })}
                        />
                    )}
                    <FilterChips
                        filters={filters}
                        projectLabel={filters.project === null ? '' : projectName(filters.project, projectNames)}
                        annotatorLabel={annotatorLabel(filters.annotator, shownOverview)}
                        onChange={onAddressChange as (change: Partial<Filters>) => void}
                    />
                    {refresh ? <FreshnessStamp refresh={refresh} timeZone={timeZone} /> : null}
                </div>
            ) : null}
            {refresh ? <StaleWarning refresh={refresh} timeZone={timeZone} /> : null}
            <HistoryProgress history={history} />
            {content}
        </div>
    );
}
