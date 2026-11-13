// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';
import Spin from 'antd/lib/spin';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';

import { PageState } from './service';
import TeamAnalyticsErrorPanel from './error-panel';
import WorkingTimeByAnnotatorCard from './cards/working-time-by-annotator-card';

interface Props {
    // slug of the organization selected in CVAT, null for none
    organization: string | null;
    state: PageState;
    onBackToTasks?: () => void;
}

function scopeLabel(organization: string | null, state: PageState): string {
    if (organization) return `Organization ${organization}`;
    // without an organization only an administrator reads instance scope
    if (state.kind === 'select-organization') return 'No organization selected';
    return 'All organizations and personal workspaces';
}

// Presentational: renders one page state. Data loading lives in team-analytics-page.tsx.
export default function TeamAnalyticsView({ organization, state, onBackToTasks }: Props): JSX.Element {
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
            <div className='cvat-team-analytics-cards'>
                <WorkingTimeByAnnotatorCard rows={state.overview.by_annotator.rows} />
            </div>
        );
    }

    return (
        <div className='cvat-team-analytics-page'>
            <div className='cvat-team-analytics-header'>
                <Title level={4}>Team analytics</Title>
                <Text type='secondary'>
                    {scopeLabel(organization, state)}
                    {' · annotation work inside jobs'}
                </Text>
            </div>
            {content}
        </div>
    );
}
