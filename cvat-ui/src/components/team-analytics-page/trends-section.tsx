// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './trends.scss';
import React, { useEffect, useState } from 'react';

import {
    CompareKind, ProjectNames, TrendStep, Trends, requestService, loadTrends,
} from './service';
import { Compared, addCompared, removeCompared } from './trends';
import { lookupProjectNames } from './project-names';
import TrendsCard from './cards/trends-card';

interface Props {
    organization: string | null;
    timeZone: string;
    // the page's filters and shape switch; the period is deliberately not here
    project: number | null;
    annotator: number | null;
    shapes: 'bounding_boxes' | 'all';
    scopeLabel: string;
    projectNames?: ProjectNames;
    // changes as history is processed (status `history`), so withheld weeks are asked for again
    historyProgress?: string;
    // the selection kept by the page, so that it survives opening a chart's full view and coming back
    selection?: TrendsSelection;
    // the metric key of the chart shown alone in its full view
    full?: string | null;
    onOpenFull?: (metric: string) => void;
}

export interface TrendsSelection {
    step: TrendStep;
    setStep: (step: TrendStep) => void;
    kind: CompareKind;
    setKind: (kind: CompareKind) => void;
    compared: Compared[];
    setCompared: React.Dispatch<React.SetStateAction<Compared[]>>;
}

// Weeks or months and what is compared; held by whoever must keep it (the page, or the section itself).
export function useTrendsSelection(): TrendsSelection {
    const [step, setStep] = useState<TrendStep>('week');
    const [kind, setKind] = useState<CompareKind>('annotators');
    const [compared, setCompared] = useState<Compared[]>([]);
    return {
        step, setStep, kind, setKind, compared, setCompared,
    };
}

// The trends card with its own selection (weeks or months, what is compared) and its own request: trends
// follow the organization, the filters and the shape switch, never the selected period.
export default function TrendsSection({
    organization, timeZone, project, annotator, shapes, scopeLabel, projectNames = {}, historyProgress = '',
    selection, full = null, onOpenFull,
}: Props): JSX.Element {
    const own = useTrendsSelection();
    const {
        step, setStep, kind, setKind, compared, setCompared,
    } = selection ?? own;
    const [query, setQuery] = useState('');
    const [trends, setTrends] = useState<Trends | null>(null);
    const [failed, setFailed] = useState(false);
    const [pending, setPending] = useState(false);
    const [annotatorNames, setAnnotatorNames] = useState<Record<number, string>>({});
    const [names, setNames] = useState<ProjectNames>({});

    const ids = compared.map((item) => item.id);
    const idsKey = ids.join(',');
    useEffect(() => {
        let current = true;
        setPending(true);
        loadTrends({
            organization, timeZone, project, annotator, shapes, step, compare: kind, ids,
        }, requestService).then((next) => {
            if (!current) return;
            setPending(false);
            setFailed(next === null);
            // a failed read keeps the shown trends (if any) rather than blanking the card
            if (next) {
                setTrends(next);
                const seen: Record<number, string> = {};
                if (next.compare === 'annotators') {
                    for (const row of next.candidates) if (row.user_name) seen[row.id] = row.user_name;
                }
                for (const line of next.lines) if (line.id !== null && line.user_name) seen[line.id] = line.user_name;
                setAnnotatorNames((known) => ({ ...known, ...seen }));
            }
        });
        return () => { current = false; };
    }, [organization, timeZone, project, annotator, shapes, step, kind, idsKey, historyProgress]);

    // names of the projects that can be compared (the fork's project-names lookup)
    const known = { ...projectNames, ...names };
    const wanted = trends && trends.compare === 'projects' ?
        [...new Set([...trends.candidates.map((row) => row.id), ...ids])]
            .filter((id) => id > 0 && !(id in known)).sort((a, b) => a - b) : [];
    const wantedKey = wanted.join(',');
    useEffect(() => {
        if (wanted.length === 0) return undefined;
        let current = true;
        lookupProjectNames(wanted, requestService).then((found) => {
            if (current) setNames((shown) => ({ ...shown, ...found }));
        }).catch(() => { /* shown by identifier */ });
        return () => { current = false; };
    }, [wantedKey]);

    return (
        <TrendsCard
            trends={trends}
            failed={failed}
            pending={(pending || failed) && !!trends}
            step={step}
            onStep={setStep}
            kind={kind}
            onKind={(next) => {
                setKind(next);
                setCompared([]);
                setQuery('');
            }}
            compared={compared}
            onAdd={(id) => {
                setCompared((shown) => addCompared(shown, id));
                setQuery('');
            }}
            onRemove={(id) => setCompared((shown) => removeCompared(shown, id))}
            query={query}
            onQuery={setQuery}
            scopeLabel={scopeLabel}
            projectNames={known}
            annotatorNames={annotatorNames}
            full={full}
            onOpenFull={onOpenFull}
        />
    );
}
