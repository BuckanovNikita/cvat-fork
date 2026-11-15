// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import {
    Details, DetailsKind, DetailsRow, ProjectNames,
} from '../service';
import {
    MISSING, exactHours, formatCount, formatHours, formatSeconds, formatShare, projectName,
} from '../format';
import { Term } from '../definitions';

interface Props {
    // null until the first answer
    details: Details | null;
    by: DetailsKind;
    onBy?: (by: DetailsKind) => void;
    search: string;
    onSearch?: (search: string) => void;
    onPage?: (page: number) => void;
    // the page's filter on the table's own dimension (marked), or null
    selected: number | null;
    onPick?: (id: number) => void;
    projectNames?: ProjectNames;
    failed?: boolean;
    pending?: boolean;
}

const KINDS: { key: DetailsKind; label: string }[] = [
    { key: 'annotators', label: 'Annotators' },
    { key: 'projects', label: 'Projects' },
];

const NOT_RECORDED = 'Not recorded';

function rowName(row: DetailsRow, by: DetailsKind, names: ProjectNames): string {
    if (by === 'projects') return projectName(row.id, names);
    return row.user_name || `Annotator #${row.id}`;
}

function pagerLabel(details: Details): string {
    const first = (details.page - 1) * details.page_size + 1;
    return `${first}–${first + details.rows.length - 1} of ${formatCount(details.total)}`;
}

// The details table: every figure for every annotator or every project, ten rows a page, searchable by
// name, sorted by working time. Clicking a row sets it as the page's filter.
function DetailsTableCard({
    details, by, onBy, search, onSearch, onPage, selected, onPick, projectNames = {}, failed = false,
    pending = false,
}: Props): JSX.Element {
    const finding = by === 'projects';
    // the rows are of the kind the answer is for (the previous kind while a switch loads)
    const projects = (details?.by ?? by) === 'projects';
    const legacy = !!details?.legacy;
    const pages = details ? Math.max(1, Math.ceil(details.total / details.page_size)) : 1;
    const shown = details && details.processed !== false ? details : null;

    let body: JSX.Element | null = null;
    if (!details) {
        body = failed ? <p className='cvat-team-analytics-details-note'>Details could not be loaded.</p> : null;
    } else if (details.processed === false) {
        body = <p className='cvat-team-analytics-details-note'>This period is not processed yet.</p>;
    } else if (details.total === 0) {
        body = (
            <p className='cvat-team-analytics-details-note'>
                {search.trim() ? 'No match for this search.' : 'No job work in this period'}
            </p>
        );
    }

    return (
        <section
            className={`cvat-team-analytics-card cvat-team-analytics-details${pending ? ' cvat-team-analytics-pending' : ''}`}
            aria-busy={pending}
        >
            <div className='cvat-team-analytics-details-header'>
                <h2 className='cvat-team-analytics-details-title'>Details</h2>
                <div role='group' aria-label='Table rows' className='cvat-team-analytics-trends-segments'>
                    {KINDS.map((option) => (
                        <button
                            key={option.key}
                            type='button'
                            aria-pressed={option.key === by}
                            onClick={() => onBy?.(option.key)}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
                <input
                    type='search'
                    className='cvat-team-analytics-details-search'
                    aria-label={finding ? 'Find a project' : 'Find an annotator'}
                    placeholder={finding ? 'Find a project' : 'Find an annotator'}
                    value={search}
                    onChange={(event) => onSearch?.(event.target.value)}
                />
                <span className='cvat-team-analytics-details-hint'>Sorted by working time</span>
            </div>
            {failed && details ? (
                <p className='cvat-team-analytics-details-note'>Details could not be updated; the table shows the previous choice.</p>
            ) : null}
            {shown && shown.total > 0 ? (
                <div className='cvat-team-analytics-table-scroll'>
                    <table className='cvat-team-analytics-table cvat-team-analytics-details-table'>
                        <thead>
                            <tr>
                                <th className='cvat-team-analytics-details-name'>{projects ? 'Project' : 'Annotator'}</th>
                                <th>{projects ? 'Annotators' : 'Projects'}</th>
                                <th><Term name='Session'>Sessions</Term></th>
                                <th><Term name='Working time'>Working time</Term></th>
                                <th>Drawn</th>
                                <th>Pasted</th>
                                <th>Propagated</th>
                                <th>{legacy ? 'Boxes saved' : <Term name='Model'>Model</Term>}</th>
                                <th>Alignments</th>
                                <th>Class changes</th>
                                <th>Deletions</th>
                                <th><Term name='Time per operation'>Avg time to create</Term></th>
                                <th>Hotkey share</th>
                            </tr>
                        </thead>
                        <tbody>
                            {shown.rows.map((row) => {
                                const name = rowName(row, projects ? 'projects' : 'annotators', projectNames);
                                const on = row.id === selected;
                                return (
                                    <tr
                                        key={row.id}
                                        className={`cvat-team-analytics-details-row${on ? ' cvat-team-analytics-details-selected' : ''}`}
                                        onClick={() => onPick?.(row.id)}
                                    >
                                        <th scope='row' className='cvat-team-analytics-details-name'>
                                            <button type='button' aria-pressed={on} title={name}>{name}</button>
                                        </th>
                                        <td>{formatCount((projects ? row.annotators : row.projects) ?? 0)}</td>
                                        <td>{formatCount(row.sessions)}</td>
                                        <td title={exactHours(row.working_time_ms)}>
                                            {formatHours(row.working_time_ms)}
                                        </td>
                                        <td>{formatCount(row.drawn)}</td>
                                        <td>{formatCount(row.pasted)}</td>
                                        <td>{formatCount(row.propagated)}</td>
                                        <td>{formatCount(legacy ? row.saved_boxes : row.model)}</td>
                                        <td>{formatCount(row.alignments)}</td>
                                        {legacy ? (
                                            <td className='cvat-team-analytics-not-recorded'>{NOT_RECORDED}</td>
                                        ) : (
                                            <td>{formatCount(row.class_changes)}</td>
                                        )}
                                        <td>{formatCount(row.deletions)}</td>
                                        <td>{formatSeconds(row.average_create_ms)}</td>
                                        {legacy ? (
                                            <td className='cvat-team-analytics-not-recorded'>{NOT_RECORDED}</td>
                                        ) : (
                                            <td>
                                                {row.hotkey_share === null ? MISSING : formatShare(row.hotkey_share)}
                                            </td>
                                        )}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ) : body}
            {shown && shown.total > 0 ? (
                <div className='cvat-team-analytics-details-pager'>
                    <span>{pagerLabel(shown)}</span>
                    {pages > 1 ? (
                        <>
                            <button
                                type='button'
                                disabled={shown.page <= 1}
                                onClick={() => onPage?.(shown.page - 1)}
                            >
                                Previous
                            </button>
                            <button
                                type='button'
                                disabled={shown.page >= pages}
                                onClick={() => onPage?.(shown.page + 1)}
                            >
                                Next
                            </button>
                        </>
                    ) : null}
                    {shown.technical_accounts ? (
                        <span className='cvat-team-analytics-details-hint'>
                            {`${shown.technical_accounts} technical account${shown.technical_accounts === 1 ? ' is' : 's are'} left out of annotator lists`}
                        </span>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
}

export default React.memo(DetailsTableCard);
