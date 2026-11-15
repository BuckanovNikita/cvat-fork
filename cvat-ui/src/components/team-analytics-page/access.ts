// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Who reads Team Analytics: administrators only. The API checks the same before it returns anything; the page
// uses this to show the "not available" panel at once, and the header to decide whether the link is shown.
export interface TeamAnalyticsLinkInput {
    // `plugins.list.ANALYTICS`: analytics is enabled on the server
    analyticsEnabled: boolean;
    // the user's groups as CVAT reports them (`user.groups`)
    groups: readonly string[] | null | undefined;
}

// Whether the signed-in account (its groups as CVAT reports them) may read Team Analytics.
export function isTeamAnalyticsReader(groups: readonly string[] | null | undefined): boolean {
    return (groups ?? []).includes('admin');
}

export function canOpenTeamAnalytics({ analyticsEnabled, groups }: TeamAnalyticsLinkInput): boolean {
    return analyticsEnabled && isTeamAnalyticsReader(groups);
}
