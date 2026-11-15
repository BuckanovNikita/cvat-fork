// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Project names for the page, asked of CVAT's own API through cvat-core with the viewer's session, so the
// page shows only names CVAT would show this viewer (cvat-core adds the selected organization). The
// analytics service returns identifiers only. Tests replace this module.

import { getCore } from 'cvat-core-wrapper';

import { ProjectNames } from './service';

// Projects asked per request: the ids go into the request line, which proxies and CVAT cap (often at
// 8-16 KB); 100 ids of up to 8 digits stay well under that, and within CVAT's largest page (500).
export const NAMES_PER_REQUEST = 100;

export async function lookupProjectNames(ids: number[]): Promise<ProjectNames> {
    const wanted = [...new Set(ids.filter((id) => id > 0))];
    const chunks: number[][] = [];
    for (let start = 0; start < wanted.length; start += NAMES_PER_REQUEST) {
        chunks.push(wanted.slice(start, start + NAMES_PER_REQUEST));
    }
    const names: ProjectNames = {};
    let failure: unknown = null;
    // one request at a time; a failed one leaves only its own projects shown by identifier
    for (const chunk of chunks) {
        try {
            // CVAT v2.82.0 lists `id` among the project filter fields; one page holds the chunk
            const projects = await getCore().projects.get({
                filter: JSON.stringify({ in: [{ var: 'id' }, chunk] }),
                pageSize: chunk.length,
            });
            for (const project of projects) names[project.id] = project.name;
        } catch (error) {
            failure = error;
        }
    }
    if (failure !== null && Object.keys(names).length === 0) throw failure;
    return names;
}
