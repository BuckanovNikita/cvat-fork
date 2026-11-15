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

// The request line stays under 4096 characters, a common limit of servers and proxies: the `ids` parameter,
// counted with its commas encoded (`%2C`, three characters), is at most this long; the path and `org` fit in the
// rest. With long ids this limit, not NAMES_PER_REQUEST, ends a request (300 ids of seven digits).
export const IDS_CHARACTERS_PER_REQUEST = 3000;

// `ids` in requests of at most NAMES_PER_REQUEST ids and IDS_CHARACTERS_PER_REQUEST characters each
export function namesChunks(ids: number[]): number[][] {
    const chunks: number[][] = [];
    let chunk: number[] = [];
    let characters = 0;
    for (const id of ids) {
        const digits = String(id).length;
        if (chunk.length && (chunk.length === NAMES_PER_REQUEST ||
            characters + 3 + digits > IDS_CHARACTERS_PER_REQUEST)) {
            chunks.push(chunk);
            chunk = [];
            characters = 0;
        }
        // a comma before every id but the first
        characters += (chunk.length ? 3 : 0) + digits;
        chunk.push(id);
    }
    if (chunk.length) chunks.push(chunk);
    return chunks;
}

// The names of the existing projects among `ids`. `answered`, when given, receives the ids of the requests that
// were answered (named or not), also when the lookup then throws because a request failed and none named a project:
// an id there without a name names no project, while the ids of a failed request may be asked again.
export async function lookupProjectNames(
    ids: number[], request: RequestService = requestService, answered?: Set<number>,
): Promise<ProjectNames> {
    const wanted = [...new Set(ids.filter((id) => Number.isInteger(id) && id > 0))];
    const chunks = namesChunks(wanted);
    const names: ProjectNames = {};
    let failure: unknown = null;
    // one request at a time; a failed one leaves only its own projects shown by identifier
    for (const chunk of chunks) {
        try {
            Object.assign(names, await requestProjectNames(chunk, request));
            chunk.forEach((id) => answered?.add(id));
        } catch (error) {
            failure = error;
        }
    }
    if (failure !== null && Object.keys(names).length === 0) throw failure;
    return names;
}
