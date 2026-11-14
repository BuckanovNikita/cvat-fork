// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useState } from 'react';

import { BarPart } from './operations';

// The toolbar, list and table of a full view: every row, searchable and sortable by value or by name, with
// names shown whole. Rank and share belong to the row (given over all rows), so a found row keeps them.

export interface FullListRow {
    key: string;
    id: number;
    rank: number;
    name: string;
    // a second column (a hotkey's keys)
    extra?: string;
    // text the search looks in besides the name
    searchText?: string;
    // bar length relative to the largest row (0..1)
    width: number;
    parts: BarPart[];
    value: string;
    share: string;
    title: string;
}

export interface FullTableRow {
    key: string;
    name: string;
    cells: string[];
}

export type Sort = 'value' | 'name';

function Segmented<T extends string>({
    label, options, value, onChange,
}: {
    label: string;
    options: { key: T; label: string }[];
    value: T;
    onChange?: (key: T) => void;
}): JSX.Element {
    return (
        <div role='group' aria-label={label} className='cvat-team-analytics-full-segments'>
            {options.map((option) => (
                <button
                    key={option.key}
                    type='button'
                    aria-pressed={option.key === value}
                    onClick={() => (option.key !== value && onChange ? onChange(option.key) : undefined)}
                >
                    {option.label}
                </button>
            ))}
        </div>
    );
}

export type RowsKind = 'annotators' | 'projects';

interface ToolbarProps {
    placeholder: string;
    query: string;
    onQuery: (query: string) => void;
    sort: Sort;
    onSort: (sort: Sort) => void;
    // the switch between annotators and projects, for charts that have it
    rowsKind?: RowsKind;
    onRows?: (rows: RowsKind) => void;
    summary?: string;
}

function Toolbar({
    placeholder, query, onQuery, sort, onSort, rowsKind, onRows, summary,
}: ToolbarProps): JSX.Element {
    return (
        <div className='cvat-team-analytics-full-toolbar'>
            <input
                type='search'
                className='cvat-team-analytics-full-search'
                aria-label={placeholder}
                placeholder={placeholder}
                value={query}
                onChange={(event) => onQuery(event.target.value)}
            />
            <Segmented
                label='Sort'
                options={[{ key: 'value', label: 'By value' }, { key: 'name', label: 'By name' }] as { key: Sort; label: string }[]}
                value={sort}
                onChange={onSort}
            />
            {rowsKind && onRows ? (
                <Segmented
                    label='Rows'
                    options={[{ key: 'annotators', label: 'Annotators' }, { key: 'projects', label: 'Projects' }] as
                        { key: RowsKind; label: string }[]}
                    value={rowsKind}
                    onChange={onRows}
                />
            ) : null}
            {summary ? <span className='cvat-team-analytics-full-summary'>{summary}</span> : null}
        </div>
    );
}

// The rows a search and a sort leave, in order; rows come in the service's order (largest first).
export function arrange<T extends { name: string; searchText?: string }>(rows: T[], query: string, sort: Sort): T[] {
    const typed = query.trim().toLowerCase();
    const found = rows.filter((row) => `${row.name} ${row.searchText ?? ''}`.toLowerCase().includes(typed));
    return sort === 'name' ? [...found].sort((a, b) => a.name.localeCompare(b.name)) : found;
}

function NoMatch(): JSX.Element {
    return <div className='cvat-team-analytics-full-no-match'>No match for this search.</div>;
}

interface ListProps extends Omit<ToolbarProps, 'query' | 'onQuery' | 'sort' | 'onSort'> {
    legend: React.ReactNode;
    nameHeader: string;
    extraHeader?: string;
    valueHeader: string;
    rows: FullListRow[];
    selected?: number | null;
    // clicking a row sets the page's filter, as on the overview
    onPick?: (id: number) => void;
}

export function FullList({
    legend, nameHeader, extraHeader, valueHeader, rows, selected = null, onPick, ...toolbar
}: ListProps): JSX.Element {
    const [query, setQuery] = useState('');
    const [sort, setSort] = useState<Sort>('value');
    const shown = arrange(rows, query, sort);
    const withExtra = extraHeader !== undefined;
    return (
        <>
            <Toolbar {...toolbar} query={query} onQuery={setQuery} sort={sort} onSort={setSort} />
            {legend}
            <div className='cvat-team-analytics-full-scroll'>
                <div className={`cvat-team-analytics-full-list${withExtra ? ' cvat-team-analytics-full-list-extra' : ''}`}>
                    <div className='cvat-team-analytics-full-list-header'>
                        <span className='cvat-team-analytics-full-rank'>#</span>
                        <span>{nameHeader}</span>
                        {withExtra ? <span>{extraHeader}</span> : null}
                        <span />
                        <span className='cvat-team-analytics-full-value'>{valueHeader}</span>
                        <span className='cvat-team-analytics-full-share'>Share</span>
                    </div>
                    {shown.map((row) => (
                        <button
                            type='button'
                            key={row.key}
                            className={`cvat-team-analytics-full-list-row${
                                row.id === selected && onPick ? ' cvat-team-analytics-selected' : ''}`}
                            aria-pressed={onPick ? row.id === selected : undefined}
                            title={row.title}
                            onClick={onPick ? () => onPick(row.id) : undefined}
                        >
                            <span className='cvat-team-analytics-full-rank'>{String(row.rank)}</span>
                            <span className='cvat-team-analytics-full-name'>{row.name}</span>
                            {withExtra ? <span className='cvat-team-analytics-full-extra'>{row.extra ?? ''}</span> : null}
                            <span className='cvat-team-analytics-full-bar'>
                                <span className='cvat-team-analytics-full-bar-fill' style={{ width: `${row.width * 100}%` }}>
                                    {row.parts.map((part) => (
                                        <span
                                            key={part.key}
                                            className='cvat-team-analytics-full-bar-part'
                                            title={part.title}
                                            style={{ flex: `${part.grow} 1 0`, background: part.color }}
                                        />
                                    ))}
                                </span>
                            </span>
                            <span className='cvat-team-analytics-full-value'>{row.value}</span>
                            <span className='cvat-team-analytics-full-share'>{row.share}</span>
                        </button>
                    ))}
                </div>
            </div>
            {shown.length === 0 && rows.length > 0 ? <NoMatch /> : null}
        </>
    );
}

interface TableProps extends Omit<ToolbarProps, 'query' | 'onQuery' | 'sort' | 'onSort'> {
    nameHeader: string;
    columns: string[];
    rows: FullTableRow[];
}

export function FullTable({
    nameHeader, columns, rows, ...toolbar
}: TableProps): JSX.Element {
    const [query, setQuery] = useState('');
    const [sort, setSort] = useState<Sort>('value');
    const shown = arrange(rows, query, sort);
    return (
        <>
            <Toolbar {...toolbar} query={query} onQuery={setQuery} sort={sort} onSort={setSort} />
            <div className='cvat-team-analytics-full-scroll'>
                <table className='cvat-team-analytics-full-table'>
                    <thead>
                        <tr>
                            <th scope='col'>{nameHeader}</th>
                            {columns.map((column) => <th key={column} scope='col'>{column}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {shown.map((row) => (
                            <tr key={row.key}>
                                <th scope='row'>{row.name}</th>
                                {row.cells.map((cell, index) => <td key={index}>{cell}</td>)}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {shown.length === 0 && rows.length > 0 ? <NoMatch /> : null}
        </>
    );
}
