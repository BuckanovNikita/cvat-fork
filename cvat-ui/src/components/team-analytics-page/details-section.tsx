// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './details.scss';
import React, { useEffect, useState } from 'react';

import {
    Details, DetailsKind, ProjectNames, requestService, loadDetails,
} from './service';
import { projectName } from './format';
import { lookupProjectNames } from './project-names';
import DetailsTableCard from './cards/details-table-card';

interface Props {
    organization: string | null;
    timeZone: string;
    period: string;
    month: string | null;
    // the page's filters: the one on the table's own dimension marks a row, the other narrows the table
    project: number | null;
    annotator: number | null;
    shapes: 'bounding_boxes' | 'all';
    projectNames?: ProjectNames;
    // a row was clicked: set it as the page's annotator or project filter
    onPick?: (kind: 'annotator' | 'project', id: number) => void;
}

// Rows of one table page (the service's page size).
const PAGE_SIZE = 10;

// The projects whose name, as the page shows it, contains the search text (CVAT's names are known only here).
export function matchingProjects(ids: number[], names: ProjectNames, search: string): number[] {
    const wanted = search.trim().toLowerCase();
    return ids.filter((id) => projectName(id, names).toLowerCase().includes(wanted));
}

// The details table with its own choice (annotators or projects, search, page) and its own request.
export default function DetailsSection({
    organization, timeZone, period, month, project, annotator, shapes, projectNames = {}, onPick,
}: Props): JSX.Element {
    const [by, setBy] = useState<DetailsKind>('annotators');
    const [search, setSearch] = useState('');
    const [page, setPage] = useState(1);
    const [details, setDetails] = useState<Details | null>(null);
    const [failed, setFailed] = useState(false);
    const [pending, setPending] = useState(false);
    const [names, setNames] = useState<ProjectNames>({});
    // every project of the table before the search, from the last answer by project
    const [allProjects, setAllProjects] = useState<number[]>([]);

    // only the filter on the other dimension narrows the table; the one on its own dimension marks a row, so
    // picking a row keeps the page shown
    const narrowing = by === 'annotators' ?
        { project, annotator: null } : { project: null, annotator };
    const scopeKey = [organization, period, month, narrowing.project, narrowing.annotator, shapes].join('|');
    // a new scope starts again from the first page
    useEffect(() => { setPage(1); }, [scopeKey]);

    const known = { ...projectNames, ...names };
    const searching = search.trim() !== '';
    // A project search is paged here: the service lists `project_ids` in the table's order, so the page
    // asks for one page of matching projects at a time and the request stays small for any number of them.
    const matches = by === 'projects' && searching ? matchingProjects(allProjects, known, search) : null;
    const lastPage = matches === null ? page : Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
    const shownPage = Math.min(page, lastPage);
    const ids = matches === null ? null : matches.slice((shownPage - 1) * PAGE_SIZE, shownPage * PAGE_SIZE);
    const idsKey = ids === null ? '-' : ids.join(',');
    const text = by === 'annotators' ? search.trim() : '';

    useEffect(() => {
        let current = true;
        setPending(true);
        loadDetails({
            organization,
            timeZone,
            period,
            month,
            ...narrowing,
            shapes,
            by,
            page: matches === null ? page : 1,
            search: text,
            ids,
        }, requestService).then((next) => {
            if (!current) return;
            setPending(false);
            setFailed(next === null);
            if (next) {
                setDetails(next);
                if (next.by === 'projects' && next.project_ids) {
                    const fresh = next.project_ids;
                    setAllProjects((shown) => (shown.join(',') === fresh.join(',') ? shown : fresh));
                }
            }
        });
        return () => { current = false; };
    }, [scopeKey, timeZone, by, matches === null ? page : 0, text, idsKey]);

    // names of the shown projects, and of every project while searching by name
    const wanted = by === 'projects' ? [...new Set([
        // a table without figures (a period not wholly processed) has no rows to name
        ...(details?.by === 'projects' && details.rows ? details.rows.map((row) => row.id) : []),
        ...(searching ? allProjects : []),
    ])].filter((id) => id > 0 && !(id in known)).sort((a, b) => a - b) : [];
    const wantedKey = wanted.join(',');
    useEffect(() => {
        if (wanted.length === 0) return undefined;
        let current = true;
        lookupProjectNames(wanted).then((found) => {
            if (current) setNames((shown) => ({ ...shown, ...found }));
        }).catch(() => { /* shown by identifier */ });
        return () => { current = false; };
    }, [wantedKey]);

    // the table of the kind chosen; until its first answer arrives the previous one stays dimmed
    // (while a project search is paged here, its page and total are the page's own)
    const shown = details && matches !== null && details.by === 'projects' ?
        { ...details, page: shownPage, total: matches.length } : details;
    return (
        <DetailsTableCard
            details={shown}
            by={by}
            onBy={(next) => {
                if (next === by) return;
                setBy(next);
                setSearch('');
                setPage(1);
            }}
            search={search}
            onSearch={(next) => {
                setSearch(next);
                setPage(1);
            }}
            onPage={setPage}
            selected={(shown ? shown.by : by) === 'projects' ? project : annotator}
            onPick={(id) => onPick?.((shown ? shown.by : by) === 'projects' ? 'project' : 'annotator', id)}
            projectNames={known}
            failed={failed}
            pending={(pending || failed) && !!details}
        />
    );
}
