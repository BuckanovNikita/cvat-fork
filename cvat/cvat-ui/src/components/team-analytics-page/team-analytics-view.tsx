// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';
import Spin from 'antd/lib/spin';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';

import { Overview, PageState, ProjectNames } from './service';
import { Filters } from './filters';
import { projectName } from './format';
import TeamAnalyticsErrorPanel from './error-panel';
import FilterChips from './filter-chips';
import WorkingTimeByAnnotatorCard from './cards/working-time-by-annotator-card';
import WorkingTimeByProjectCard from './cards/working-time-by-project-card';
import AnnotatorsCard from './cards/annotators-card';
import SessionsCard from './cards/sessions-card';

interface Props {
    // slug of the organization selected in CVAT, null for none
    organization: string | null;
    state: PageState;
    onBackToTasks?: () => void;
    // the project and annotator filters kept in the page address; without them rows are not clickable
    filters?: Filters;
    onFiltersChange?: (change: Partial<Filters>) => void;
    // names of the shown projects as CVAT returns them to the viewer
    projectNames?: ProjectNames;
}

const NO_FILTERS: Filters = { project: null, annotator: null };

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
    organization, state, onBackToTasks, filters = NO_FILTERS, onFiltersChange, projectNames = {},
}: Props): JSX.Element {
    // clicking a row sets it as the filter; clicking the selected row again removes it
    const pick = (key: keyof Filters) => (onFiltersChange ? (id: number): void => {
        onFiltersChange({ [key]: filters[key] === id ? null : id });
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
    } else {
        const { overview } = state;
        const annotatorRest = overview.by_annotator.rest?.count ?? 0;
        content = (
            <div className='cvat-team-analytics-cards'>
                {overview.headline ? (
                    <AnnotatorsCard
                        annotators={overview.headline.annotators}
                        projects={overview.headline.projects}
                        of={filters.annotator === null ? null : overview.by_annotator.rows.length + annotatorRest}
                        projectSelected={filters.project !== null}
                    />
                ) : null}
                {overview.sessions ? <SessionsCard figures={overview.sessions} /> : null}
                {overview.by_project ? (
                    <WorkingTimeByProjectCard
                        rows={overview.by_project.rows}
                        rest={overview.by_project.rest}
                        names={projectNames}
                        selected={filters.project}
                        onPick={pick('project')}
                    />
                ) : null}
                <WorkingTimeByAnnotatorCard
                    rows={overview.by_annotator.rows}
                    rest={overview.by_annotator.rest}
                    selected={filters.annotator}
                    onPick={pick('annotator')}
                />
            </div>
        );
    }

    const showFilterChips = !!onFiltersChange && ['ready', 'loading', 'error'].includes(state.kind);
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
            {showFilterChips ? (
                <FilterChips
                    filters={filters}
                    projectLabel={filters.project === null ? '' : projectName(filters.project, projectNames)}
                    annotatorLabel={annotatorLabel(filters.annotator, shownOverview)}
                    onChange={onFiltersChange as (change: Partial<Filters>) => void}
                />
            ) : null}
            {content}
        </div>
    );
}
