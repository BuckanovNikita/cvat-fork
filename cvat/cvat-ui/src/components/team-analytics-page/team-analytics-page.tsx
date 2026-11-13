// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import React, {
    useEffect, useMemo, useRef, useState,
} from 'react';
import { useSelector } from 'react-redux';
import { useHistory } from 'react-router';

import { CombinedState } from 'reducers';
import {
    PageState, Status, fetchService, loadOverview, loadStatus, viewerTimeZone,
} from './service';
import { currentMonth, useAddress } from './address';
import { agedStatus } from './freshness';
import TeamAnalyticsView from './team-analytics-view';

// The status (last refresh) is read again this often while the page is open.
const STATUS_INTERVAL_MS = 60000;

// The page, loaded on demand by team-analytics-route.tsx. It reads the organization CVAT has
// selected and the selection kept in the page address, asks the service for its figures and
// status; everything it shows is in TeamAnalyticsView.
export default function TeamAnalyticsPage(): JSX.Element {
    const organization = useSelector((state: CombinedState) => state.organizations.current?.slug ?? null);
    const history = useHistory();
    const [address, changeAddress] = useAddress(history);
    const timeZone = useMemo(viewerTimeZone, []);
    const [state, setState] = useState<PageState>({ kind: 'loading' });
    const [pending, setPending] = useState(false);
    const [status, setStatus] = useState<Status | null>(null);
    const shownOrganization = useRef<string | null>(organization);

    useEffect(() => {
        let current = true;
        // a new selection keeps the shown figures (dimmed) until the new ones arrive; another
        // organization never shows the previous one's figures
        const sameOrganization = shownOrganization.current === organization;
        shownOrganization.current = organization;
        setState((shown) => (shown.kind === 'ready' && sameOrganization ? shown : { kind: 'loading' }));
        setPending(true);
        loadOverview({
            organization, timeZone, period: address.period, month: address.month,
        }, fetchService).then((next) => {
            if (!current) return;
            setState(next);
            setPending(false);
        });
        return () => { current = false; };
    }, [organization, address.period, address.month]);

    const ready = state.kind === 'ready';
    useEffect(() => {
        if (!ready) return undefined;
        let current = true;
        // the last status read for this organization and when it arrived, by the page's clock
        let last: { status: Status; at: number } | null = null;
        const load = (): void => {
            loadStatus({ organization, timeZone }, fetchService).then((next) => {
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
        />
    );
}
