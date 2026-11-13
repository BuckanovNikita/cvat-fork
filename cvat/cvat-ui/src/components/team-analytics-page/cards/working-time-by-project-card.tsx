// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { ProjectNames, ProjectWorkingTime, Rest } from '../service';
import { projectName } from '../format';
import WorkingTimeBreakdown from './working-time-breakdown';

interface Props {
    rows: ProjectWorkingTime[];
    rest?: Rest;
    names: ProjectNames;
    selected?: number | null;
    onPick?: (projectId: number) => void;
}

// Working time per project: the largest rows (within the annotator filter) and the rest as one line.
function WorkingTimeByProjectCard({
    rows, rest, names, selected, onPick,
}: Props): JSX.Element {
    return (
        <WorkingTimeBreakdown
            kind='project'
            title='Working time by project'
            subtitle='Last 7 days'
            rows={rows.map((row) => ({
                id: row.project_id, name: projectName(row.project_id, names), working_time_ms: row.working_time_ms,
            }))}
            rest={rest}
            selected={selected}
            onPick={onPick}
        />
    );
}

export default React.memo(WorkingTimeByProjectCard);
