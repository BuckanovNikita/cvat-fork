// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import './projects-filters.scss';
import React, {
    useEffect, useMemo, useRef, useState,
} from 'react';
import { useSelector } from 'react-redux';
import { useHistory } from 'react-router';

import { CombinedState } from 'reducers';
import {
    PageState, ProjectNames, Status, requestService, loadOverview, loadStatus, onRefusal, viewerTimeZone,
} from './service';
import { currentMonth, useAddress } from './address';
import { agedStatus } from './freshness';
import { monthAvailable, periodAvailable } from './history';
import { lookupProjectNames } from './project-names';
import { hotkeyLabels } from './hotkeys';
import TeamAnalyticsView from './team-analytics-view';
import TrendsSection, { useTrendsSelection } from './trends-section';
import DetailsSection from './details-section';

// The status (last refresh) is read again this often while the page is open.
const STATUS_INTERVAL_MS = 60000;

// The page, loaded on demand by team-analytics-route.tsx. It reads the organization CVAT has
// selected and the selection kept in the page address (period and filters), asks the service for
// its figures and status and CVAT for the shown projects' names; everything it shows is in
// TeamAnalyticsView.
export default function TeamAnalyticsPage(): JSX.Element {
    const organization = useSelector((state: CombinedState) => state.organizations.current?.slug ?? null);
    const history = useHistory();
    // hotkeys are labelled with the viewer's own keymap
    const shortcuts = useSelector((state: CombinedState) => state.shortcuts);
    const labels = useMemo(() => hotkeyLabels(shortcuts), [shortcuts]);
    // filters picked in another organization are not applied (filters.ts)
    const [address, changeAddress] = useAddress(history, organization);
    const timeZone = useMemo(viewerTimeZone, []);
    const [state, setState] = useState<PageState>({ kind: 'loading' });
    const [pending, setPending] = useState(false);
    const [status, setStatus] = useState<Status | null>(null);
    const [projectNames, setProjectNames] = useState<ProjectNames>({});
    // bumped to load the figures of the same selection again
    const [reloads, setReloads] = useState(0);
    const shownOrganization = useRef<string | null>(organization);
    // kept here so that a trend's full view and the overview show the same comparison
    const trendsSelection = useTrendsSelection();

    useEffect(() => {
        let current = true;
        // a new selection keeps the shown figures (dimmed) until the new ones arrive; another
        // organization never shows the previous one's figures
        const sameOrganization = shownOrganization.current === organization;
        shownOrganization.current = organization;
        setState((shown) => (shown.kind === 'ready' && sameOrganization ? shown : { kind: 'loading' }));
        setPending(true);
        loadOverview({
            organization,
            timeZone,
            period: address.period,
            month: address.month,
            project: address.project,
            annotator: address.annotator,
            shapes: address.shapes,
        }, requestService).then((next) => {
            if (!current) return;
            setState(next);
            setPending(false);
        });
        return () => { current = false; };
    }, [organization, address.period, address.month, address.project, address.annotator, address.shapes, reloads]);

    // a refusal of any other request (trends, details, a full view's list, the status poll) means the caller
    // may no longer read: the whole page shows that refusal instead of the figures it already has
    useEffect(() => onRefusal((refusal) => {
        setState(refusal);
        setPending(false);
    }), []);

    // the shown period was not wholly processed; once a status read says it is, its figures are loaded
    const waitingForHistory = state.kind === 'ready' && state.overview.processed === false;
    useEffect(() => {
        if (!waitingForHistory || !status?.history) return;
        const available = address.period === 'month' && address.month ?
            monthAvailable(status.history, address.month) : periodAvailable(status.history, address.period);
        if (available) setReloads((count) => count + 1);
    }, [status]);

    const ready = state.kind === 'ready';
    useEffect(() => {
        if (!ready) return undefined;
        let current = true;
        // the last status read for this organization and when it arrived, by the page's clock
        let last: { status: Status; at: number } | null = null;
        const load = (): void => {
            loadStatus({ organization, timeZone }, requestService).then((next) => {
                if (!current) return;
                if (next) {
                    last = { status: next, at: Date.now() };
                    setStatus(next);
                } else {
                    // a failed read keeps the last time shown and lets it age until it is stale
                    setStatus(last ? agedStatus(last.status, Date.now() - last.at) : null);
                }
            });
        };
        load();
        const timer = setInterval(load, STATUS_INTERVAL_MS);
        return () => {
            current = false;
            clearInterval(timer);
        };
    }, [organization, ready]);

    // names for the shown projects and the selected one; without an answer projects show their identifiers
    const shownProjects = state.kind === 'ready' ? (state.overview.by_project?.rows ?? []).map((row) => row.project_id) : [];
    if (address.project !== null) shownProjects.push(address.project);
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
            address={address}
            onAddressChange={changeAddress}
            currentMonth={currentMonth()}
            pending={pending}
            status={status}
            timeZone={timeZone}
            projectNames={projectNames}
            hotkeyLabels={labels}
            renderTrends={(scopeLabel, options) => (
                <TrendsSection
                    organization={organization}
                    timeZone={timeZone}
                    project={address.project}
                    annotator={address.annotator}
                    shapes={address.shapes}
                    scopeLabel={scopeLabel}
                    projectNames={projectNames}
                    historyProgress={status?.history ?
                        [
                            status.history.complete, status.history.ready_from, status.history.percent,
                            status.history.complete_weeks, status.history.earliest_month,
                        ].join('|') : ''}
                    selection={trendsSelection}
                    full={options?.full}
                    onOpenFull={options?.onOpenFull}
                />
            )}
            renderDetails={() => (
                <DetailsSection
                    organization={organization}
                    timeZone={timeZone}
                    period={address.period}
                    month={address.month}
                    project={address.project}
                    annotator={address.annotator}
                    shapes={address.shapes}
                    projectNames={projectNames}
                    // clicking a row sets it as the filter; clicking the selected row again removes it
                    onPick={(kind, id) => changeAddress({ [kind]: address[kind] === id ? null : id })}
                />
            )}
        />
    );
}
