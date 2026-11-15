// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { ProjectNames, ProjectWorkingTime, Rest } from '../service';
import { projectName } from '../format';
import WorkingTimeBreakdown from './working-time-breakdown';
import { Term } from '../definitions';

interface Props {
    rows: ProjectWorkingTime[];
    rest?: Rest;
    // the rows' legacy flag: class change is no part of the split
    legacy?: boolean;
    names: ProjectNames;
    selected?: number | null;
    onPick?: (projectId: number) => void;
    // the selected period as the page names it
    periodLabel?: string;
    onFullView?: () => void;
}

// Working time per project: the largest rows (within the annotator filter) and the rest as one line.
function WorkingTimeByProjectCard({
    rows, rest, legacy = false, names, selected, onPick, periodLabel = 'Last 7 days', onFullView,
}: Props): JSX.Element {
    return (
        <WorkingTimeBreakdown
            kind='project'
            title={<><Term name='Working time'>Working time</Term> by project</>}
            subtitle={periodLabel}
            rows={rows.map((row) => ({
                id: row.project_id,
                name: projectName(row.project_id, names),
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

export default React.memo(WorkingTimeByProjectCard);
