// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Who is offered Team Analytics in the header: administrators only. The API checks the same before it
// returns anything; this only decides whether the link is shown.
export interface TeamAnalyticsLinkInput {
    // `plugins.list.ANALYTICS`: analytics is enabled on the server
    analyticsEnabled: boolean;
    // the user's groups as CVAT reports them (`user.groups`)
    groups: readonly string[] | null | undefined;
}

export function canOpenTeamAnalytics({ analyticsEnabled, groups }: TeamAnalyticsLinkInput): boolean {
    return analyticsEnabled && (groups ?? []).includes('admin');
}
