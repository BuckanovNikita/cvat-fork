// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { Filters } from './filters';

interface Props {
    filters: Filters;
    // the names to show for the selected project and annotator
    projectLabel: string;
    annotatorLabel: string;
    onChange: (change: Partial<Filters>) => void;
}

function Chip({
    kind, label, value, active, onClear,
}: {
    kind: string; label: string; value: string; active: boolean; onClear: () => void;
}): JSX.Element {
    return (
        <span
            className={`cvat-team-analytics-filter cvat-team-analytics-filter-${kind}${
                active ? ' cvat-team-analytics-filter-active' : ''}`}
            title={value}
        >
            <span className='cvat-team-analytics-filter-label'>{label}</span>
            <span className='cvat-team-analytics-filter-value'>{value}</span>
            {active ? (
                <button
                    type='button'
                    className='cvat-team-analytics-filter-clear'
                    aria-label={`Show all ${kind === 'project' ? 'projects' : 'annotators'}`}
                    title={`Show all ${kind === 'project' ? 'projects' : 'annotators'}`}
                    onClick={onClear}
                >
                    ×
                </button>
            ) : null}
        </span>
    );
}

// The project and annotator filters of the filter row; each shows what is selected and clears it.
export default function FilterChips({
    filters, projectLabel, annotatorLabel, onChange,
}: Props): JSX.Element {
    return (
        <div className='cvat-team-analytics-filter-chips'>
            <Chip
                kind='project'
                label='Project'
                value={filters.project === null ? 'All projects' : projectLabel}
                active={filters.project !== null}
                onClear={() => onChange({ project: null })}
            />
            <Chip
                kind='annotator'
                label='Annotator'
                value={filters.annotator === null ? 'All annotators' : annotatorLabel}
                active={filters.annotator !== null}
                onClear={() => onChange({ annotator: null })}
            />
        </div>
    );
}
