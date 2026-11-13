// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import './projects-filters.scss';
import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { useHistory } from 'react-router';

import { CombinedState } from 'reducers';
import {
    PageState, ProjectNames, fetchService, loadOverview, viewerTimeZone,
} from './service';
import { useFilters } from './filters';
import { lookupProjectNames } from './project-names';
import TeamAnalyticsView from './team-analytics-view';

// The page, loaded on demand by team-analytics-route.tsx. It reads the organization CVAT has
// selected and the filters kept in the page address, asks the service for its figures and CVAT for
// the shown projects' names; everything it shows is in TeamAnalyticsView.
export default function TeamAnalyticsPage(): JSX.Element {
    const organization = useSelector((state: CombinedState) => state.organizations.current?.slug ?? null);
    const history = useHistory();
    const [filters, changeFilters] = useFilters(history);
    const [state, setState] = useState<PageState>({ kind: 'loading' });
    const [projectNames, setProjectNames] = useState<ProjectNames>({});

    useEffect(() => {
        let current = true;
        setState({ kind: 'loading' });
        loadOverview({
            organization, timeZone: viewerTimeZone(), project: filters.project, annotator: filters.annotator,
        }, fetchService).then((next) => {
            if (current) setState(next);
        });
        return () => { current = false; };
    }, [organization, filters.project, filters.annotator]);

    // names for the shown projects and the selected one; without an answer projects show their identifiers
    const shownProjects = state.kind === 'ready' ? (state.overview.by_project?.rows ?? []).map((row) => row.project_id) : [];
    if (filters.project !== null) shownProjects.push(filters.project);
    const wanted = [...new Set(shownProjects.filter((id) => id > 0 && !(id in projectNames)))].sort((a, b) => a - b);
    const wantedKey = wanted.join(',');
    useEffect(() => {
        if (wanted.length === 0) return undefined;
        let current = true;
        lookupProjectNames(wanted).then((names) => {
            if (current) setProjectNames((known) => ({ ...known, ...names }));
        }).catch(() => { /* shown by identifier */ });
        return () => { current = false; };
    }, [wantedKey]);

    return (
        <TeamAnalyticsView
            organization={organization}
            state={state}
            onBackToTasks={() => history.push('/tasks')}
            filters={filters}
            onFiltersChange={changeFilters}
            projectNames={projectNames}
        />
    );
}
