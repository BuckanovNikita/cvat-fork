// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { AnnotatorWorkingTime, Rest } from '../service';
import WorkingTimeBreakdown from './working-time-breakdown';
import { Term } from '../definitions';

interface Props {
    rows: AnnotatorWorkingTime[];
    rest?: Rest;
    // the rows' legacy flag: class change is no part of the split
    legacy?: boolean;
    selected?: number | null;
    onPick?: (userId: number) => void;
    // the selected period as the page names it
    periodLabel?: string;
    onFullView?: () => void;
}

// Working time per annotator: the largest rows (within the project filter) and the rest as one line.
function WorkingTimeByAnnotatorCard({
    rows, rest, legacy = false, selected, onPick, periodLabel = 'Last 7 days', onFullView,
}: Props): JSX.Element {
    return (
        <WorkingTimeBreakdown
            kind='annotator'
            title={<><Term name='Working time'>Working time</Term> by annotator</>}
            subtitle={periodLabel}
            rows={rows.map((row) => ({
                id: row.user_id,
                name: row.user_name,
                working_time_ms: row.working_time_ms,
                operations: row.operations,
            }))}
            rest={rest}
            legacy={legacy}
            selected={selected}
            onPick={onPick}
            onFullView={onFullView}
        />
    );
}

export default React.memo(WorkingTimeByAnnotatorCard);
