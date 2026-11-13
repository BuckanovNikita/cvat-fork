// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Project names for the page, asked of CVAT's own API through cvat-core with the viewer's session, so the
// page shows only names CVAT would show this viewer (cvat-core adds the selected organization). The
// analytics service returns identifiers only. Tests replace this module.

import { getCore } from 'cvat-core-wrapper';

import { ProjectNames } from './service';

export async function lookupProjectNames(ids: number[]): Promise<ProjectNames> {
    const wanted = [...new Set(ids.filter((id) => id > 0))];
    if (wanted.length === 0) return {};
    // CVAT v2.82.0 lists `id` among the project filter fields; one page holds every wanted project
    const projects = await getCore().projects.get({
        filter: JSON.stringify({ in: [{ var: 'id' }, wanted] }),
        pageSize: wanted.length,
    });
    const names: ProjectNames = {};
    for (const project of projects) names[project.id] = project.name;
    return names;
}
