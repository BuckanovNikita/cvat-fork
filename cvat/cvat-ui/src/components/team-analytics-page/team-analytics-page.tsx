// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { useHistory } from 'react-router';

import { CombinedState } from 'reducers';
import {
    PageState, fetchService, loadOverview, viewerTimeZone,
} from './service';
import TeamAnalyticsView from './team-analytics-view';

// The page, loaded on demand by team-analytics-route.tsx. It reads the organization CVAT has
// selected and asks the service for its figures; everything it shows is in TeamAnalyticsView.
export default function TeamAnalyticsPage(): JSX.Element {
    const organization = useSelector((state: CombinedState) => state.organizations.current?.slug ?? null);
    const history = useHistory();
    const [state, setState] = useState<PageState>({ kind: 'loading' });

    useEffect(() => {
        let current = true;
        setState({ kind: 'loading' });
        loadOverview({ organization, timeZone: viewerTimeZone() }, fetchService).then((next) => {
            if (current) setState(next);
        });
        return () => { current = false; };
    }, [organization]);

    return (
        <TeamAnalyticsView
            organization={organization}
            state={state}
            onBackToTasks={() => history.push('/tasks')}
        />
    );
}
