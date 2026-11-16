// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './full-view.scss';
import React, { useEffect, useState } from 'react';

import {
    FullList as ListResponse, HotkeysList, ListKind, Overview, ProjectNames, RowsList, requestService, loadList,
} from './service';
import { Address } from './address';
import { FullView as FullViewKey, FullViewRows, trendOfView } from './full-views';
import {
    MISSING, dayLabel, exactHours, formatCount, formatHours, formatSeconds, formatShare, projectName,
} from './format';
import { OPERATION_LOOKS, operationParts, splitParts } from './operations';
import { shapeWording } from './shapes';
import { HotkeyLabels, hotkeyLabel } from './hotkeys';
import { lookupProjectNames } from './project-names';
import { NotProcessedNotice } from './history';
import { FullList, FullListRow, FullTable } from './full-view-list';
import WorkingTimeOverPeriodCard from './cards/working-time-over-period-card';

const HOTKEY_COLOR = '#2a78d6';
const WORKING_TIME_COLOR = '#2a78d6';

interface Props {
    view: FullViewKey;
    rows: FullViewRows;
    overview: Overview;
    organization: string | null;
    timeZone: string;
    address: Address;
    onAddressChange: (change: Partial<Address>) => void;
    // the period as the page names it, and who and where the figures cover
    periodLabel: string;
    who: string;
    where: string;
    projectNames?: ProjectNames;
    hotkeyLabels?: HotkeyLabels;
    // a trend chart alone (by its metric key), rendered by the trends section
    renderTrend?: (metric: string) => React.ReactNode;
}

function Legend({ children, hint }: { children: React.ReactNode; hint?: string }): JSX.Element {
    return (
        <div className='cvat-team-analytics-full-legend'>
            <span className='cvat-team-analytics-full-legend-label'>Bar colours</span>
            {children}
            {hint ? <span className='cvat-team-analytics-full-legend-hint'>{hint}</span> : null}
        </div>
    );
}

function Swatch({ color, name }: { color: string; name: string }): JSX.Element {
    return (
        <span className='cvat-team-analytics-full-legend-item'>
            <span className='cvat-team-analytics-swatch' style={{ background: color }} />
            {name}
        </span>
    );
}

function WorkingTimeList({
    list, kind, names, selected, onPick, onRows, summaryNoun,
}: {
    list: RowsList;
    kind: FullViewKey;
    names: ProjectNames;
    selected: number | null;
    onPick: (id: number) => void;
    onRows?: (rows: FullViewRows) => void;
    summaryNoun: string;
}): JSX.Element {
    const projects = list.by === 'projects';
    // a row with no working time (e.g. a project with only Model boxes) belongs to the tables, not here
    const worked = list.rows.filter((row) => row.working_time_ms > 0);
    const largest = Math.max(0, ...worked.map((row) => row.working_time_ms));
    const rows: FullListRow[] = worked.map((row, index) => {
        const name = projects ? projectName(row.id, names) : row.user_name ?? `Annotator #${row.id}`;
        return {
            key: String(row.id),
            id: row.id,
            rank: index + 1,
            name,
            width: largest > 0 ? row.working_time_ms / largest : 0,
            parts: operationParts(row.operations, name, list.legacy),
            value: formatHours(row.working_time_ms),
            share: formatShare(row.share),
            title: `${name}: ${exactHours(row.working_time_ms)}`,
        };
    });
    return (
        <FullList
            placeholder={projects ? 'Find a project' : 'Find an annotator'}
            rows={rows}
            nameHeader={projects ? 'Project' : 'Annotator'}
            valueHeader='Working time'
            selected={selected}
            onPick={onPick}
            rowsKind={kind === 'split' ? list.by : undefined}
            onRows={kind === 'split' ? onRows : undefined}
            summary={
                `${formatCount(worked.length)} ${summaryNoun} · ${formatHours(list.total.working_time_ms)} in total`
            }
            legend={(
                <Legend hint='Select a row to filter the whole page.'>
                    {splitParts(list.legacy).map((key) => (
                        <Swatch key={key} color={OPERATION_LOOKS[key].color} name={OPERATION_LOOKS[key].name} />
                    ))}
                </Legend>
            )}
        />
    );
}

function HotkeysFullList({ list, labels }: { list: HotkeysList; labels?: HotkeyLabels }): JSX.Element {
    const largest = Math.max(0, ...list.rows.map((row) => row.actions));
    const rows: FullListRow[] = list.rows.map((row, index) => {
        const label = hotkeyLabel(row.action, labels);
        return {
            key: row.action,
            id: index,
            rank: index + 1,
            name: label.name,
            extra: label.keys,
            searchText: label.keys,
            width: largest > 0 ? Math.max(0.005, row.actions / largest) : 0,
            parts: [{
                key: 'hotkey', color: HOTKEY_COLOR, grow: 1, title: `${label.name} (${label.keys}): ${formatCount(row.actions)}`,
            }],
            value: formatCount(row.actions),
            share: formatShare(row.share),
            title: `${label.name} (${label.keys}): ${formatCount(row.actions)}`,
        };
    });
    return (
        <FullList
            placeholder='Find an action or key'
            rows={rows}
            nameHeader='Action'
            extraHeader='Key'
            valueHeader='Actions'
            summary={`${formatCount(list.rows.length)} hotkeys · ${formatCount(list.hotkey_actions)} actions`}
            legend={<Legend><Swatch color={HOTKEY_COLOR} name='Hotkey actions' /></Legend>}
        />
    );
}

function OperationsTable({
    list, kind, names, onRows, summaryNoun,
}: {
    list: RowsList;
    kind: 'operations' | 'methods';
    names: ProjectNames;
    onRows: (rows: FullViewRows) => void;
    summaryNoun: string;
}): JSX.Element {
    const projects = list.by === 'projects';
    const count = (value: number): string => formatCount(value);
    const columns = kind === 'operations' ?
        ['Created', 'Avg create', 'Aligned', 'Avg align', 'Class changes', 'Avg change', 'Deleted', 'Avg delete'] :
        ['Drawn', 'Avg drawn', 'Pasted', 'Avg pasted', 'Propagated', 'Avg propagated', 'Model', 'All annotator methods',
            'Avg all'];
    const rows = list.rows.map((row) => {
        const { operations: ops, methods } = row;
        let cells: string[];
        if (kind === 'operations') {
            const classChange = list.legacy ? ['Not recorded', MISSING] :
                [count(ops.class_change.objects), formatSeconds(ops.class_change.average_ms)];
            cells = [
                count(ops.creation.objects), formatSeconds(ops.creation.average_ms),
                count(ops.alignment.objects), formatSeconds(ops.alignment.average_ms),
                ...classChange,
                count(ops.deletion.objects), formatSeconds(ops.deletion.average_ms),
            ];
        } else {
            cells = [
                count(methods.drawn.objects), formatSeconds(methods.drawn.average_ms),
                count(methods.pasted.objects), formatSeconds(methods.pasted.average_ms),
                count(methods.propagated.objects), formatSeconds(methods.propagated.average_ms),
                count(row.model), count(ops.creation.objects), formatSeconds(ops.creation.average_ms),
            ];
        }
        return {
            key: String(row.id),
            name: projects ? projectName(row.id, names) : row.user_name ?? `Annotator #${row.id}`,
            cells,
        };
    });
    return (
        <FullTable
            placeholder={projects ? 'Find a project' : 'Find an annotator'}
            nameHeader={projects ? 'Project' : 'Annotator'}
            columns={columns}
            rows={rows}
            rowsKind={list.by}
            onRows={onRows}
            summary={`${formatCount(list.total.count)} ${summaryNoun}`}
        />
    );
}

function TimeFullView({ overview }: { overview: Overview }): JSX.Element {
    const series = overview.time_series;
    if (!series) return <div className='cvat-team-analytics-full-message'>No working time figures</div>;
    const weekly = series.unit === 'week';
    return (
        <>
            <Legend><Swatch color={WORKING_TIME_COLOR} name='Working time' /></Legend>
            <WorkingTimeOverPeriodCard series={series} large />
            <div className='cvat-team-analytics-full-values-title'>All values</div>
            <ul className='cvat-team-analytics-full-values'>
                {series.buckets.map((bucket) => (
                    <li key={bucket.start} title={exactHours(bucket.working_time_ms)}>
                        <span>{`${weekly ? 'Week of ' : ''}${dayLabel(bucket.start)}`}</span>
                        <span className='cvat-team-analytics-full-value'>{formatHours(bucket.working_time_ms)}</span>
                    </li>
                ))}
            </ul>
        </>
    );
}

// Loads one list for a full view (and the names of its projects), following the address.
function useList(by: ListKind | null, organization: string | null, timeZone: string, address: Address): {
    list: ListResponse | null; failed: boolean; pending: boolean;
} {
    const [list, setList] = useState<ListResponse | null>(null);
    const [failed, setFailed] = useState(false);
    const [pending, setPending] = useState(false);
    useEffect(() => {
        if (!by) return undefined;
        let current = true;
        setPending(true);
        loadList({
            organization,
            timeZone,
            period: address.period,
            month: address.month,
            project: address.project,
            annotator: address.annotator,
            shapes: address.shapes,
            by,
        }, requestService).then((next) => {
            if (!current) return;
            setPending(false);
            setFailed(next === null);
            // a list of another kind is never shown for this one
            setList((shown) => next ?? (shown?.by === by ? shown : null));
        });
        return () => { current = false; };
    }, [by, organization, timeZone, address.period, address.month, address.project, address.annotator, address.shapes]);
    return { list: list && list.by === by ? list : null, failed, pending };
}

function listKind(view: FullViewKey, rows: FullViewRows): ListKind | null {
    if (view === 'annotators' || view === 'projects' || view === 'hotkeys') return view;
    if (view === 'split' || view === 'operations' || view === 'methods') return rows;
    return null;
}

// One chart alone on the page with every row, in place of the overview. The header and the filter row stay
// above it (team-analytics-view.tsx), so the period, the shape switch and the filters still apply.
export default function FullView({
    view, rows: rowsKind, overview, organization, timeZone, address, onAddressChange, periodLabel, who, where,
    projectNames = {}, hotkeyLabels, renderTrend,
}: Props): JSX.Element {
    const by = listKind(view, rowsKind);
    const { list, failed, pending } = useList(by, organization, timeZone, address);
    const [names, setNames] = useState<ProjectNames>({});
    const known = { ...projectNames, ...names };

    // names of every listed project (the fork's project-names lookup)
    // a list without figures (a period not wholly processed) has no rows to name
    const wanted = list && list.by === 'projects' && list.rows ?
        [...new Set(list.rows.map((row) => row.id))]
            .filter((id) => id > 0 && !(id in known))
            .sort((a, b) => a - b) : [];
    const wantedKey = wanted.join(',');
    useEffect(() => {
        if (wanted.length === 0) return undefined;
        let current = true;
        lookupProjectNames(wanted, requestService).then((found) => {
            if (current) setNames((shown) => ({ ...shown, ...found }));
        }).catch(() => { /* shown by identifier */ });
        return () => { current = false; };
    }, [wantedKey]);

    const byProjects = by === 'projects';
    const dimension = byProjects ? 'project' : 'annotator';
    const other = byProjects ? who : where;
    const wording = shapeWording({ shapes: list && list.by !== 'hotkeys' ? list.shapes : address.shapes });
    const trend = trendOfView(view);

    let title: string | null;
    let subtitle: string;
    if (view === 'time') {
        title = overview.time_series?.unit === 'week' ? 'Working time by week' : 'Working time by day';
        subtitle = `${periodLabel} · hours as the server counts working time · ${who} · ${where}`;
    } else if (trend) {
        // the trend chart names itself from the trends it shows
        title = null;
        subtitle = `${who} · ${where}`;
    } else if (view === 'hotkeys') {
        title = 'Hotkey usage';
        subtitle = `${periodLabel} · hotkey actions per action · ${who} · ${where}`;
    } else if (view === 'operations') {
        title = `${wording.operations}, by ${dimension}`;
        subtitle = `${periodLabel} · counts and average time per ${wording.noun} · ${other}`;
    } else if (view === 'methods') {
        title = `How ${wording.nouns.toLowerCase()} are created, by ${dimension}`;
        subtitle = `${periodLabel} · counts and average time per ${wording.noun} · ${other}`;
    } else {
        title = view === 'split' ? `Where working time goes, by ${dimension}` : `Working time by ${dimension}`;
        subtitle = `${periodLabel} · hours split by operation · ${other}`;
    }

    const pick = (key: 'project' | 'annotator') => (id: number): void => {
        onAddressChange({ [key]: address[key] === id ? null : id });
    };
    const onRows = (next: FullViewRows): void => onAddressChange({ rows: next });

    let body: React.ReactNode;
    if (view === 'time') {
        body = <TimeFullView overview={overview} />;
    } else if (trend) {
        body = renderTrend?.(trend) ?? null;
    } else if (!list) {
        body = (
            <div className='cvat-team-analytics-full-message' role='status'>
                {failed ? 'The list could not be loaded. It is asked for again when the selection changes.' : 'Loading…'}
            </div>
        );
    } else if (list.processed === false) {
        body = <NotProcessedNotice />;
    } else if (list.by === 'hotkeys') {
        body = <HotkeysFullList list={list} labels={hotkeyLabels} />;
    } else if (view === 'operations' || view === 'methods') {
        body = (
            <OperationsTable
                list={list}
                kind={view}
                names={known}
                onRows={onRows}
                summaryNoun={byProjects ? 'projects' : 'annotators'}
            />
        );
    } else {
        body = (
            <WorkingTimeList
                list={list}
                kind={view}
                names={known}
                selected={address[dimension]}
                onPick={pick(dimension)}
                onRows={onRows}
                summaryNoun={byProjects ? 'projects' : 'annotators'}
            />
        );
    }

    // a failed reload keeps the shown rows, dimmed and marked as not updated
    const stale = !!list && (pending || failed) && by !== null;
    return (
        <section
            className={`cvat-team-analytics-full-view${stale ? ' cvat-team-analytics-pending' : ''}`}
            aria-busy={pending}
        >
            <div className='cvat-team-analytics-full-header'>
                <button
                    type='button'
                    className='cvat-team-analytics-full-back'
                    onClick={() => onAddressChange({ view: null })}
                >
                    <svg aria-hidden width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2.2'>
                        <path d='M15 6l-6 6 6 6' />
                    </svg>
                    Back to overview
                </button>
                <div className='cvat-team-analytics-full-heading'>
                    {title ? <h2 className='cvat-team-analytics-full-title'>{title}</h2> : null}
                    <div className='cvat-team-analytics-full-subtitle'>{subtitle}</div>
                </div>
            </div>
            {list && failed && by !== null ? (
                <div className='cvat-team-analytics-full-failed' role='status'>
                    The list could not be updated; it shows the previous selection.
                </div>
            ) : null}
            {body}
        </section>
    );
}
