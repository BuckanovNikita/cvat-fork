// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';
import Spin from 'antd/lib/spin';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';
import Button from 'antd/lib/button';
import { SettingOutlined } from '@ant-design/icons';

import {
    FilterKind, FilterOptions, Overview, PageState, Period, ProjectNames, Status,
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
import KeyboardMouseCard from './cards/keyboard-mouse-card';
import { HotkeyLabels } from './hotkeys';
import CreationMethodsCard from './cards/creation-methods-card';
import { LegacyNotices } from './legacy-notice';
import ShapeSwitch from './shape-switch';
import { DEFAULT_SHAPES } from './shapes';
import FullView from './full-view';
import { FullView as FullViewKey, viewOfTrend } from './full-views';

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
    // names of the shown projects (the fork's project-names lookup)
    projectNames?: ProjectNames;
    // the viewer's keymap: hotkey action -> name and keys
    hotkeyLabels?: HotkeyLabels;
    // the trends card (loads on its own); gets who and where the scope's line covers, and in a trend's full
    // view the metric key of the chart shown alone
    renderTrends?: (scopeLabel: string, options?: TrendsOptions) => React.ReactNode;
    // the details table (loads on its own); it stays on the overview and has no full view
    renderDetails?: () => React.ReactNode;
    // the options of the Project and Annotator selectors for the period shown (loaded when one opens)
    loadFilterOptions?: (kind: FilterKind) => Promise<FilterOptions>;
    // opens "Team Analytics settings"; without it the header has no Settings button
    onOpenSettings?: () => void;
    // changes when the page's data is loaded again (after a settings change): a full view loads its rows again
    reloadKey?: number;
}

export interface TrendsOptions {
    full?: string | null;
    onOpenFull?: (metric: string) => void;
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
    // an overview without figures (a period not wholly processed) has no rows; the filter echo still names them
    const shown = overview?.by_annotator?.rows.find((row) => row.user_id === id)?.user_name;
    const echoed = overview?.filters?.annotator?.user_id === id ? overview.filters.annotator.user_name : null;
    return shown ?? echoed ?? `Annotator #${id}`;
}

// Only administrators read Team Analytics: with an organization selected, organization scope; with none,
// instance scope.
function scopeLabel(organization: string | null): string {
    if (organization) return `Organization ${organization}`;
    return 'All organizations and personal workspaces';
}

// Presentational: renders one page state. Data loading lives in team-analytics-page.tsx.
export default function TeamAnalyticsView({
    organization, state, onBackToTasks, address, onAddressChange, pending = false, status = null,
    timeZone = 'UTC', currentMonth: latestMonth = currentMonth(), projectNames = {},
    hotkeyLabels, renderTrends, renderDetails, loadFilterOptions, onOpenSettings, reloadKey = 0,
}: Props): JSX.Element {
    const filters: Filters = { project: address?.project ?? null, annotator: address?.annotator ?? null };
    // clicking a row sets it as the filter; clicking the selected row again removes it
    const pick = (key: keyof Filters): ((id: number) => void) | undefined => (onAddressChange ? (id: number): void => {
        onAddressChange({ [key]: filters[key] === id ? null : id });
    } : undefined);
    // a chart's Full view button and show all control open its full view (a new history entry)
    const open = (view: FullViewKey): (() => void) | undefined => (
        onAddressChange ? (): void => onAddressChange({ view }) : undefined
    );

    if (state.kind === 'denied') {
        return (
            <div className='cvat-team-analytics-page'>
                <Result
                    className='cvat-team-analytics-denied'
                    status='403'
                    title='Team analytics is not available'
                    subTitle={'This page is for administrators of this CVAT instance. The server checks the same ' +
                        'before it returns any data, so a direct link shows nothing more.'}
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
    } else if (state.overview.processed === false) {
        // partial figures are never shown: one gate for every card
        content = <NotProcessedNotice />;
    } else if (address?.view && onAddressChange) {
        // one chart alone with every row, in place of the overview
        const { overview } = state;
        const who = filters.annotator === null ? 'All annotators' : annotatorLabel(filters.annotator, overview);
        const where = filters.project === null ? 'All projects' : projectName(filters.project, projectNames);
        const full = (
            <FullView
                key={reloadKey}
                view={address.view}
                rows={address.rows ?? 'annotators'}
                overview={overview}
                organization={organization}
                timeZone={timeZone}
                address={address}
                onAddressChange={onAddressChange}
                periodLabel={periodLabel(shownAddress(overview.period, address), latestMonth)}
                who={who}
                where={where}
                projectNames={projectNames}
                hotkeyLabels={hotkeyLabels}
                renderTrend={(metric) => renderTrends?.(`${who} · ${where}`, { full: metric })}
            />
        );
        content = (
            <div className={`cvat-team-analytics-full${pending ? ' cvat-team-analytics-pending' : ''}`} aria-busy={pending}>
                <LegacyNotices operations={overview.operations} timeZone={timeZone} />
                {address.view.startsWith('trend-') ? <TrendsGate history={status?.history}>{full}</TrendsGate> : full}
            </div>
        );
    } else {
        const { overview } = state;
        const annotatorRest = overview.by_annotator.rest?.count ?? 0;
        const shownPeriod = periodLabel(shownAddress(overview.period, address), latestMonth);
        content = (
            <div
                className={`cvat-team-analytics-cards${pending ? ' cvat-team-analytics-pending' : ''}`}
                aria-busy={pending}
            >
                <LegacyNotices operations={overview.operations} timeZone={timeZone} />
                {overview.headline ? (
                    <AnnotatorsCard
                        annotators={overview.headline.annotators}
                        projects={overview.headline.projects}
                        of={filters.annotator === null ? null : overview.by_annotator.rows.length + annotatorRest}
                        projectSelected={filters.project !== null}
                    />
                ) : null}
                {overview.sessions ? <SessionsCard figures={overview.sessions} /> : null}
                {overview.operations ? (
                    <CreationHeadlineCards figures={overview.operations} methods={overview.creation_methods} />
                ) : null}
                {overview.time_series ? (
                    <WorkingTimeOverPeriodCard series={overview.time_series} onFullView={open('time')} />
                ) : null}
                {overview.operations ? (
                    <WorkingTimeSplitCard figures={overview.operations} onFullView={open('split')} />
                ) : null}
                {overview.operations ? (
                    <OperationsTableCard figures={overview.operations} onFullView={open('operations')} />
                ) : null}
                {overview.creation_methods ? (
                    <CreationMethodsCard
                        methods={overview.creation_methods}
                        legacy={!!overview.operations?.legacy}
                        savedBoxes={overview.saved_boxes}
                        onFullView={open('methods')}
                    />
                ) : null}
                {overview.by_project ? (
                    <WorkingTimeByProjectCard
                        rows={overview.by_project.rows}
                        rest={overview.by_project.rest}
                        legacy={!!overview.by_project.legacy}
                        names={projectNames}
                        selected={filters.project}
                        onPick={pick('project')}
                        periodLabel={shownPeriod}
                        onFullView={open('projects')}
                    />
                ) : null}
                <WorkingTimeByAnnotatorCard
                    rows={overview.by_annotator.rows}
                    rest={overview.by_annotator.rest}
                    legacy={!!overview.by_annotator.legacy}
                    selected={filters.annotator}
                    onPick={pick('annotator')}
                    periodLabel={shownPeriod}
                    onFullView={open('annotators')}
                />
                {overview.input || overview.operations?.legacy ? (
                    <KeyboardMouseCard
                        figures={overview.input ?? null}
                        legacy={!!overview.operations?.legacy}
                        labels={hotkeyLabels}
                        onFullView={open('hotkeys')}
                    />
                ) : null}
                <TrendsGate history={status?.history}>
                    {renderTrends?.([
                        filters.annotator === null ? 'All annotators' : annotatorLabel(filters.annotator, overview),
                        filters.project === null ? 'All projects' : projectName(filters.project, projectNames),
                    ].join(' · '), {
                        onOpenFull: onAddressChange ?
                            (metric) => onAddressChange({ view: viewOfTrend(metric) }) : undefined,
                    })}
                </TrendsGate>
                {renderDetails?.()}
            </div>
        );
    }

    const showFilters = !!address && !!onAddressChange && ['ready', 'loading', 'error'].includes(state.kind);
    const showSettings = !!onOpenSettings && ['ready', 'loading', 'error'].includes(state.kind);
    const refresh = state.kind === 'ready' ? status?.refresh : undefined;
    const history = state.kind === 'ready' ? status?.history : undefined;
    const shownOverview = state.kind === 'ready' ? state.overview : null;
    return (
        <div className='cvat-team-analytics-page'>
            <div className='cvat-team-analytics-header'>
                <div className='cvat-team-analytics-heading'>
                    <Title level={4}>Team analytics</Title>
                    <Text type='secondary'>
                        {scopeLabel(organization)}
                        {' · annotation work inside jobs'}
                    </Text>
                </div>
                {showSettings ? (
                    <Button
                        className='cvat-team-analytics-settings-button'
                        icon={<SettingOutlined />}
                        onClick={onOpenSettings}
                    >
                        Settings
                    </Button>
                ) : null}
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
                    {/* a legacy period has all shapes only: no switch. While the period is not fully processed,
                        `legacy` describes only its processed part and can turn to the opposite once processing
                        completes, so the switch may appear or vanish then (a recorded limit, see
                        docs/fork-specification.md, "Known limit of unprocessed periods") */}
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
                        loadOptions={loadFilterOptions}
                        optionsKey={[
                            organization ?? '', (address as Address).period, (address as Address).month ?? '', reloadKey,
                        ].join('|')}
                        projectNameOf={(id) => projectName(id, projectNames)}
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
