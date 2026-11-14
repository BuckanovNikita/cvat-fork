// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { Suspense } from 'react';
import Spin from 'antd/lib/spin';

import TeamAnalyticsErrorPanel from './error-panel';

// The page's code is fetched only when the route is opened.
const TeamAnalyticsPage = React.lazy(() => import('./team-analytics-page'));

interface BoundaryState {
    failed: boolean;
}

// Keeps a failure of the page (including a chunk that cannot be loaded) on the page itself.
class TeamAnalyticsErrorBoundary extends React.Component<React.PropsWithChildren<unknown>, BoundaryState> {
    public state: BoundaryState = { failed: false };

    public static getDerivedStateFromError(): BoundaryState {
        return { failed: true };
    }

    public componentDidCatch(error: Error): void {
        console.warn('Team analytics failed:', error);
    }

    public render(): React.ReactNode {
        const { failed } = this.state;
        const { children } = this.props;
        return failed ? <TeamAnalyticsErrorPanel /> : children;
    }
}

export default function TeamAnalyticsRoute(): JSX.Element {
    return (
        <TeamAnalyticsErrorBoundary>
            <Suspense fallback={<Spin className='cvat-team-analytics-loading' size='large' />}>
                <TeamAnalyticsPage />
            </Suspense>
        </TeamAnalyticsErrorBoundary>
    );
}
