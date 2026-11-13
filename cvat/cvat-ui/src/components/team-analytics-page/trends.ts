// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Trends and comparison: what each of the four trend charts shows, and the compared lines with the colour
// slot each keeps until it is removed.

import { Trends, TrendPoint } from './service';
import { formatCount, formatSeconds, shortCount } from './format';
import { shapeWording } from './shapes';

export const MAX_COMPARED = 5;

// one colour per slot; the scope's own line uses slot 0
export const LINE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];

export interface Compared {
    id: number;
    slot: number;
}

// Adds `id` in the lowest free slot; nothing changes at the limit or when it is already compared.
export function addCompared(compared: Compared[], id: number): Compared[] {
    if (compared.length >= MAX_COMPARED || compared.some((item) => item.id === id)) return compared;
    const slot = [0, 1, 2, 3, 4].find((free) => !compared.some((item) => item.slot === free)) as number;
    return [...compared, { id, slot }];
}

export function removeCompared(compared: Compared[], id: number): Compared[] {
    return compared.filter((item) => item.id !== id);
}

export const NOT_RECORDED = 'Not recorded';
export const NOT_PROCESSED = 'Not processed yet';

// A point as one chart reads it: a value, nothing to show, or a reason it is withheld.
export type Cell =
    | { kind: 'value'; value: number }
    | { kind: 'none' }
    | { kind: 'not-recorded' }
    | { kind: 'not-processed' };

export interface TrendMetric {
    key: string;
    title: string;
    unit: string;
    // the point's value in the chart's unit, null when there is none
    read(point: TrendPoint): Cell;
    show(value: number): string;
    // a tick of the vertical scale
    tick(value: number): string;
    // a fixed top of the scale (percent), else from the values
    top?: number;
}

const HOUR_MS = 3600000;

function hours(value: number): string {
    return `${value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} h`;
}

export function trendMetrics(trends: Pick<Trends, 'shapes' | 'step'>): TrendMetric[] {
    const wording = shapeWording(trends);
    const monthly = trends.step === 'month';
    return [
        {
            key: 'working_time',
            title: 'Working time',
            unit: monthly ? 'hours per month' : 'hours per week',
            read: (point) => ({ kind: 'value', value: point.working_time_ms / HOUR_MS }),
            show: hours,
            tick: (value) => `${value.toLocaleString('en-US')} h`,
        },
        {
            key: 'boxes',
            title: `${wording.nouns} created`,
            unit: 'drawn, pasted and propagated',
            read: (point) => (point.boxes === null ? { kind: 'not-recorded' } : { kind: 'value', value: point.boxes }),
            show: formatCount,
            tick: shortCount,
        },
        {
            key: 'average',
            title: `Average time per ${wording.noun}`,
            unit: 'seconds, all annotator methods',
            read: (point) => {
                if (point.boxes === null) return { kind: 'not-recorded' };
                return point.average_ms === null ? { kind: 'none' } : { kind: 'value', value: point.average_ms / 1000 };
            },
            show: (value) => formatSeconds(value * 1000),
            tick: (value) => `${value.toLocaleString('en-US')} s`,
        },
        {
            key: 'hotkey_share',
            title: 'Hotkey share',
            unit: 'percent of hotkey and mouse actions',
            read: (point) => {
                if (!point.hotkey_recorded) return { kind: 'not-recorded' };
                return point.hotkey_share === null ? { kind: 'none' } : { kind: 'value', value: point.hotkey_share * 100 };
            },
            show: (value) => `${Math.round(value)}%`,
            tick: (value) => `${value}%`,
            top: 100,
        },
    ];
}

// The point of a bucket as the chart shows it: withheld while the bucket is not processed.
export function cellOf(metric: TrendMetric, point: TrendPoint, processed: boolean): Cell {
    return processed ? metric.read(point) : { kind: 'not-processed' };
}

// The smallest of 1, 2, 2.5, 5 times a power of ten that is at least `max`.
export function scaleTop(max: number): number {
    if (max <= 0) return 1;
    const power = 10 ** Math.floor(Math.log10(max));
    return [1, 2, 2.5, 5, 10].map((step) => step * power).find((top) => top >= max * (1 - 1e-12)) as number;
}
