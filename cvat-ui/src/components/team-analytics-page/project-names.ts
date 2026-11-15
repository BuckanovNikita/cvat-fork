// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Project names for the page, asked of the fork's API (GET team-analytics/project-names), which names any
// project whatever its organization: Team Analytics is read by administrators only, and at instance scope
// CVAT's own projects API would name only personal-workspace projects. The figures carry identifiers only.
// Tests replace this module or the request function.

import {
    PROJECT_NAMES_PER_REQUEST, ProjectNames, RequestService, requestProjectNames, requestService,
} from './service';

export const NAMES_PER_REQUEST = PROJECT_NAMES_PER_REQUEST;

export async function lookupProjectNames(
    ids: number[], request: RequestService = requestService,
): Promise<ProjectNames> {
    const wanted = [...new Set(ids.filter((id) => Number.isInteger(id) && id > 0))];
    const chunks: number[][] = [];
    for (let start = 0; start < wanted.length; start += NAMES_PER_REQUEST) {
        chunks.push(wanted.slice(start, start + NAMES_PER_REQUEST));
    }
    const names: ProjectNames = {};
    let failure: unknown = null;
    // one request at a time; a failed one leaves only its own projects shown by identifier
    for (const chunk of chunks) {
        try {
            Object.assign(names, await requestProjectNames(chunk, request));
        } catch (error) {
            failure = error;
        }
    }
    if (failure !== null && Object.keys(names).length === 0) throw failure;
    return names;
}
