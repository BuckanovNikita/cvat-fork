// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { AnnotatorWorkingTime, Rest } from '../service';
import WorkingTimeBreakdown from './working-time-breakdown';

interface Props {
    rows: AnnotatorWorkingTime[];
    rest?: Rest;
    selected?: number | null;
    onPick?: (userId: number) => void;
}

// Working time per annotator: the largest rows (within the project filter) and the rest as one line.
function WorkingTimeByAnnotatorCard({
    rows, rest, selected, onPick,
}: Props): JSX.Element {
    return (
        <WorkingTimeBreakdown
            kind='annotator'
            title='Working time by annotator'
            subtitle='Last 7 days'
            rows={rows.map((row) => ({ id: row.user_id, name: row.user_name, working_time_ms: row.working_time_ms }))}
            rest={rest}
            selected={selected}
            onPick={onPick}
        />
    );
}

export default React.memo(WorkingTimeByAnnotatorCard);
