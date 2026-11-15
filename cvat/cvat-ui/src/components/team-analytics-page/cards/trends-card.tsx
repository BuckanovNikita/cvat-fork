// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import {
    CompareKind, ProjectNames, TrendLine, TrendStep, Trends,
} from '../service';
import { MISSING, dayLabel, projectName } from '../format';
import { FullViewButton } from '../full-view-button';
import {
    Cell, Compared, LINE_COLORS, MAX_COMPARED, NOT_PROCESSED, NOT_RECORDED, TrendMetric, cellOf, scaleTop,
    trendMetrics,
} from '../trends';

interface Props {
    // null until the first answer arrives
    trends: Trends | null;
    // the last request could not be read
    failed?: boolean;
    // new trends are loading: the shown ones stay, dimmed
    pending?: boolean;
    step: TrendStep;
    onStep?: (step: TrendStep) => void;
    kind: CompareKind;
    onKind?: (kind: CompareKind) => void;
    compared: Compared[];
    onAdd?: (id: number) => void;
    onRemove?: (id: number) => void;
    // the text typed to find someone (or a project) to compare
    query: string;
    onQuery?: (query: string) => void;
    // who and where the scope's own line covers, e.g. 'All annotators · All projects'
    scopeLabel: string;
    projectNames?: ProjectNames;
    // names of annotators the page has seen (kept for compared people who left the candidates)
    annotatorNames?: Record<number, string>;
    // opens the full view of one chart (by its metric key)
    onOpenFull?: (metric: string) => void;
    // the metric key of the chart shown alone in its full view; the card shows only that chart then
    full?: string | null;
}

// offered candidates shown at once; the rest are reached by typing
const OFFERED = 4;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function bucketName(start: string, monthly: boolean): string {
    if (!monthly) return dayLabel(start);
    const [year, month] = start.split('-').map(Number);
    return `${MONTHS[month - 1]} ${year}`;
}

function cellText(metric: TrendMetric, cell: Cell): string {
    if (cell.kind === 'value') return metric.show(cell.value);
    if (cell.kind === 'not-recorded') return NOT_RECORDED;
    if (cell.kind === 'not-processed') return NOT_PROCESSED;
    return MISSING;
}

interface ShownLine {
    key: string;
    name: string;
    color: string;
    line: TrendLine;
}

function Segmented<T extends string>({
    label, options, value, onChange,
}: {
    label: string;
    options: { key: T; label: string }[];
    value: T;
    onChange?: (key: T) => void;
}): JSX.Element {
    return (
        <div role='group' aria-label={label} className='cvat-team-analytics-trends-segments'>
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

// the values table: folded away on the overview, shown in the full view
function Values({ open, children }: { open: boolean; children: React.ReactNode }): JSX.Element {
    if (open) return <div className='cvat-team-analytics-trend-values cvat-team-analytics-trend-values-open'>{children}</div>;
    return (
        <details className='cvat-team-analytics-trend-values'>
            <summary>Values</summary>
            {children}
        </details>
    );
}

function TrendChart({
    metric, lines, trends, full = false, onOpenFull,
}: {
    metric: TrendMetric; lines: ShownLine[]; trends: Trends; full?: boolean; onOpenFull?: () => void;
}): JSX.Element {
    const monthly = trends.step === 'month';
    const count = trends.buckets.length;
    const cells = lines.map((shown) => shown.line.points.map(
        (point, index) => cellOf(metric, point, trends.buckets[index].processed),
    ));
    const all = cells.flat();
    const values = all.flatMap((cell) => (cell.kind === 'value' ? [cell.value] : []));
    const notRecorded = all.some((cell) => cell.kind === 'not-recorded');
    const top = metric.top ?? scaleTop(Math.max(0, ...values));
    const x = (index: number): number => (count > 1 ? (index / (count - 1)) * 100 : 50);
    const y = (value: number): number => (value / top) * 100;
    const step = monthly ? 2 : 3;
    // buckets where a line has nothing recorded or nothing processed, for the note under the chart
    const withheld = (kind: Cell['kind']): number => trends.buckets
        .filter((_, index) => cells.some((line) => line[index].kind === kind)).length;
    const unitName = monthly ? 'months' : 'weeks';
    // the legend: under the chart on the overview, at the top (names whole) in the full view
    const legend = (
        <ul className='cvat-team-analytics-trend-legend'>
            {lines.map((shown, lineIndex) => (
                <li key={shown.key} className='cvat-team-analytics-trend-legend-item'>
                    <span className='cvat-team-analytics-trend-swatch' style={{ background: shown.color }} aria-hidden />
                    <span className='cvat-team-analytics-trend-legend-name' title={shown.name}>{shown.name}</span>
                    <span className='cvat-team-analytics-trend-legend-value'>
                        {cellText(metric, cells[lineIndex][count - 1])}
                    </span>
                </li>
            ))}
        </ul>
    );

    return (
        <figure className={`cvat-team-analytics-trend-chart${full ? ' cvat-team-analytics-trend-chart-large' : ''}`}>
            {full ? legend : (
                <figcaption>
                    <span className='cvat-team-analytics-trend-title'>{metric.title}</span>
                    <span className='cvat-team-analytics-trend-unit'>{metric.unit}</span>
                    <FullViewButton onClick={onOpenFull} />
                </figcaption>
            )}
            {values.length === 0 && notRecorded ? (
                <div className='cvat-team-analytics-trend-empty'>Not recorded before the new logging</div>
            ) : (
                <>
                    <div className='cvat-team-analytics-trend-plot'>
                        <div className='cvat-team-analytics-trend-scale' aria-hidden>
                            {[top, top / 2, 0].map((tick) => <span key={tick}>{metric.tick(tick)}</span>)}
                        </div>
                        <div className='cvat-team-analytics-trend-area'>
                            <svg aria-hidden viewBox='0 0 100 100' preserveAspectRatio='none'>
                                {lines.map((shown, lineIndex) => {
                                    // a gap (nothing recorded, processed or measured) breaks the line
                                    let pen = 'M';
                                    const path = cells[lineIndex].map((cell, index) => {
                                        if (cell.kind !== 'value') {
                                            pen = 'M';
                                            return '';
                                        }
                                        const part = `${pen}${x(index).toFixed(2)},${(100 - y(cell.value)).toFixed(2)}`;
                                        pen = 'L';
                                        return part;
                                    }).join(' ').trim();
                                    return (
                                        <path
                                            key={shown.key}
                                            className='cvat-team-analytics-trend-line'
                                            d={path}
                                            fill='none'
                                            stroke={shown.color}
                                            strokeWidth={2}
                                            vectorEffect='non-scaling-stroke'
                                            strokeLinejoin='round'
                                            strokeLinecap='round'
                                        />
                                    );
                                })}
                            </svg>
                            {lines.map((shown, lineIndex) => cells[lineIndex].map((cell, index) => (
                                cell.kind === 'value' ? (
                                    <span
                                        key={`${shown.key}-${index}`}
                                        className={`cvat-team-analytics-trend-dot${index === count - 1 ? ' cvat-team-analytics-trend-dot-last' : ''}`}
                                        style={{
                                            left: `${x(index)}%`, bottom: `${y(cell.value)}%`, background: shown.color,
                                        }}
                                        title={`${shown.name} · ${monthly ? '' : 'week of '}${bucketName(trends.buckets[index].start, monthly)}: ${metric.show(cell.value)}`}
                                    />
                                ) : null
                            )))}
                        </div>
                    </div>
                    <div className='cvat-team-analytics-trend-axis' aria-hidden>
                        {trends.buckets.map((bucket, index) => ((count - 1 - index) % step === 0 ? (
                            <span key={bucket.start} style={{ left: `${x(index)}%` }}>
                                {bucketName(bucket.start, monthly)}
                            </span>
                        ) : null))}
                    </div>
                </>
            )}
            {withheld('not-recorded') && values.length > 0 ? (
                <div className='cvat-team-analytics-trend-note'>
                    {`Not recorded before the new logging: ${withheld('not-recorded')} of ${count} ${unitName}`}
                </div>
            ) : null}
            {withheld('not-processed') ? (
                <div className='cvat-team-analytics-trend-note'>
                    {`${NOT_PROCESSED}: ${withheld('not-processed')} of ${count} ${unitName}`}
                </div>
            ) : null}
            {full ? null : legend}
            <Values open={full}>
                <table>
                    <thead>
                        <tr>
                            <th scope='col'>{monthly ? 'Month' : 'Week'}</th>
                            {lines.map((shown) => <th key={shown.key} scope='col'>{shown.name}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {trends.buckets.map((bucket, index) => (
                            <tr key={bucket.start}>
                                <th scope='row'>{`${monthly ? '' : 'Week of '}${bucketName(bucket.start, monthly)}`}</th>
                                {lines.map((shown, lineIndex) => (
                                    <td key={shown.key}>{cellText(metric, cells[lineIndex][index])}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Values>
        </figure>
    );
}

// Trends: working time, boxes created, average time per box and hotkey share over the last twelve weeks or
// months, independent of the period. One line for the scope, or one per compared annotator or project; a
// compared line keeps the colour of its slot until it is removed.
function TrendsCard({
    trends, failed = false, pending = false, step, onStep, kind, onKind, compared, onAdd, onRemove, query, onQuery,
    scopeLabel, projectNames = {}, annotatorNames = {}, onOpenFull, full = null,
}: Props): JSX.Element {
    const projects = kind === 'projects';
    const candidates = trends && trends.compare === kind ? trends.candidates : [];
    const nameOf = (id: number): string => {
        if (projects) return projectName(id, projectNames);
        const candidate = candidates.find((row) => row.id === id)?.user_name;
        return candidate ?? annotatorNames[id] ?? `Annotator #${id}`;
    };
    const atLimit = compared.length >= MAX_COMPARED;
    const typed = query.trim().toLowerCase();
    const offered = candidates
        .filter((row) => !compared.some((item) => item.id === row.id))
        .filter((row) => nameOf(row.id).toLowerCase().includes(typed));
    let hint = '';
    if (atLimit) hint = `Up to ${MAX_COMPARED} at once. Remove one to add another.`;
    else if (trends && offered.length === 0) hint = 'No match';
    else if (offered.length > OFFERED) hint = `${offered.length - OFFERED} more match. Type to narrow the list.`;

    const lines: ShownLine[] = (trends?.lines ?? []).map((line, index) => {
        if (line.id === null) {
            return {
                key: 'scope', name: scopeLabel, color: LINE_COLORS[0], line,
            };
        }
        const slot = compared.find((item) => item.id === line.id)?.slot ?? index;
        const name = projects || trends?.compare === 'projects' ?
            projectName(line.id, projectNames) : line.user_name ?? nameOf(line.id);
        return {
            key: String(line.id), name, color: LINE_COLORS[slot % LINE_COLORS.length], line,
        };
    });

    if (full) {
        // one chart alone, large, in its full view; the selection stays as it was on the overview
        const metric = trends ? trendMetrics(trends).find((item) => item.key === full) : undefined;
        if (!trends || !metric) {
            return (
                <div className='cvat-team-analytics-trend-failed' role='status'>
                    {failed ? 'Trends could not be loaded.' : 'Loading trends…'}
                </div>
            );
        }
        return (
            <div className={`cvat-team-analytics-trend-full${pending ? ' cvat-team-analytics-pending' : ''}`}>
                <h2 className='cvat-team-analytics-full-title'>{metric.title}</h2>
                <div className='cvat-team-analytics-full-subtitle'>
                    {`${metric.unit} · last 12 ${step === 'month' ? 'months' : 'weeks'}`}
                </div>
                <TrendChart metric={metric} lines={lines} trends={trends} full />
            </div>
        );
    }

    let body: JSX.Element;
    if (trends) {
        body = (
            <>
                {failed ? (
                    <div className='cvat-team-analytics-trend-failed' role='status'>
                        Trends could not be updated; the charts show the previous choice.
                    </div>
                ) : null}
                <div className='cvat-team-analytics-trend-charts'>
                    {trendMetrics(trends).map((metric) => (
                        <TrendChart
                            key={metric.key}
                            metric={metric}
                            lines={lines}
                            trends={trends}
                            onOpenFull={onOpenFull ? () => onOpenFull(metric.key) : undefined}
                        />
                    ))}
                </div>
            </>
        );
    } else if (failed) {
        body = (
            <div className='cvat-team-analytics-trend-failed' role='status'>
                Trends could not be loaded. They are asked for again when the filters change.
            </div>
        );
    } else {
        body = <div className='cvat-team-analytics-trend-loading'>Loading trends…</div>;
    }

    return (
        <section
            className={`cvat-team-analytics-card cvat-team-analytics-trends${pending ? ' cvat-team-analytics-pending' : ''}`}
            aria-busy={pending}
        >
            <div className='cvat-team-analytics-trends-header'>
                <div>
                    <Text strong>Trends</Text>
                    <div className='cvat-team-analytics-trends-subtitle'>
                        {`Last 12 ${step === 'month' ? 'months' : 'weeks'}, independent of the period above`}
                    </div>
                </div>
                <Segmented
                    label='Trend step'
                    options={[{ key: 'week', label: 'Weeks' }, { key: 'month', label: 'Months' }]}
                    value={step}
                    onChange={onStep}
                />
                <Segmented
                    label='Compare'
                    options={[{ key: 'annotators', label: 'Annotators' }, { key: 'projects', label: 'Projects' }]}
                    value={kind}
                    onChange={onKind}
                />
            </div>
            <div className='cvat-team-analytics-compare'>
                <span className='cvat-team-analytics-compare-label'>
                    {compared.length ? 'Comparing' : `Showing ${scopeLabel}. Compare:`}
                </span>
                {compared.map((item) => {
                    const name = nameOf(item.id);
                    return (
                        <button
                            key={item.id}
                            type='button'
                            className='cvat-team-analytics-compare-chip'
                            title={`Remove ${name}`}
                            onClick={() => onRemove?.(item.id)}
                        >
                            <span
                                className='cvat-team-analytics-compare-swatch'
                                style={{ background: LINE_COLORS[item.slot] }}
                                aria-hidden
                            />
                            <span className='cvat-team-analytics-compare-name'>{name}</span>
                            <span aria-hidden>×</span>
                        </button>
                    );
                })}
                <input
                    type='search'
                    className='cvat-team-analytics-compare-search'
                    aria-label={projects ? 'Find a project' : 'Find an annotator'}
                    placeholder={projects ? 'Find a project' : 'Find an annotator'}
                    disabled={atLimit}
                    value={query}
                    onChange={(event) => onQuery?.(event.target.value)}
                />
                {offered.slice(0, OFFERED).map((row) => {
                    const name = nameOf(row.id);
                    return (
                        <button
                            key={row.id}
                            type='button'
                            className='cvat-team-analytics-compare-offer'
                            disabled={atLimit}
                            title={atLimit ? 'Remove one to add another' : `Add ${name}`}
                            onClick={() => onAdd?.(row.id)}
                        >
                            {`+ ${name}`}
                        </button>
                    );
                })}
                {hint ? <span className='cvat-team-analytics-compare-hint'>{hint}</span> : null}
            </div>
            {body}
        </section>
    );
}

export default React.memo(TrendsCard);
