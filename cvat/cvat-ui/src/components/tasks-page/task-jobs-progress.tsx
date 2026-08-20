// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import { TaskJobsSummary } from 'reducers';

interface Props {
    summary: TaskJobsSummary;
    totalJobs: number;
}

interface Segment {
    className: string;
    label: string;
    count: number;
}

function TaskJobsProgress(props: Props): JSX.Element {
    const { summary, totalJobs } = props;

    // A user may have access to a subset of the task jobs only,
    // the rest is still displayed to keep the bar consistent with the total counter
    const inaccessibleJobs = Math.max(0, totalJobs - summary.fetched);
    const segments: Segment[] = [
        { className: 'cvat-jobs-progress-annotation-new', label: 'Not started', count: summary.annotationNew },
        { className: 'cvat-jobs-progress-annotating', label: 'Annotating', count: summary.annotating },
        { className: 'cvat-jobs-progress-validation', label: 'On review', count: summary.validation },
        { className: 'cvat-jobs-progress-acceptance', label: 'Accepted', count: summary.acceptance },
        { className: 'cvat-jobs-progress-rejected', label: 'Rejected', count: summary.rejected },
        { className: 'cvat-jobs-progress-inaccessible', label: 'Not available', count: inaccessibleJobs },
    ].filter((segment: Segment) => segment.count > 0);

    return (
        <div className='cvat-task-item-jobs-progress'>
            {segments.map(({ className, label, count }: Segment) => (
                <div
                    key={className}
                    className={`cvat-task-item-jobs-progress-segment ${className}`}
                    style={{ flexGrow: count }}
                    title={`${label}: ${count}`}
                />
            ))}
        </div>
    );
}

export default React.memo(TaskJobsProgress);
