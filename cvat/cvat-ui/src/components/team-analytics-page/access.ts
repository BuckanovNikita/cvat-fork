// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Who is offered Team Analytics in the header. The analytics service checks the same roles with
// CVAT before it returns anything; this only decides whether the link is shown.
export interface TeamAnalyticsLinkInput {
    // `plugins.list.ANALYTICS`: analytics is enabled on the server
    analyticsEnabled: boolean;
    // the user's groups as CVAT reports them (`user.groups`)
    groups: readonly string[] | null | undefined;
    // the user's role in the current organization (`organizations.currentRole`), null without one
    currentRole: string | null | undefined;
}

const READING_ROLES = ['owner', 'maintainer'];

export function canOpenTeamAnalytics({ analyticsEnabled, groups, currentRole }: TeamAnalyticsLinkInput): boolean {
    if (!analyticsEnabled) return false;
    if ((groups ?? []).includes('admin')) return true;
    return !!currentRole && READING_ROLES.includes(currentRole);
}
