// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';
import { JobStage, JobState } from 'cvat-core-wrapper';
import { TaskJobsSummary } from 'reducers';
import { TASK_JOB_COLORS } from 'utils/task-jobs-summary';

interface Props {
    summary: TaskJobsSummary;
    totalJobs: number;
}

interface Bucket {
    key: string;
    label: string;
    count: number;
    color: string;
}

function TaskJobsProgress(props: Props): JSX.Element {
    const { summary, totalJobs } = props;

    // A user may have access to a subset of the task jobs only,
    // the rest is still displayed to keep the widget consistent with the total counter
    const inaccessibleJobs = Math.max(0, totalJobs - summary.fetched);
    const buckets: Bucket[] = [
        ...Object.values(JobStage).flatMap((stage) => Object.values(JobState).map((state) => ({
            key: `${stage}-${state.replace(/ /g, '-')}`,
            label: `${stage} / ${state}`,
            count: summary.counts[stage][state],
            color: TASK_JOB_COLORS[stage][state],
        }))),
        { key: 'inaccessible', label: 'not available', count: inaccessibleJobs, color: '#c1c1c1' },
    ].filter((bucket: Bucket) => bucket.count > 0);

    return (
        <>
            <div>
                {buckets.map(({ key, label, count, color }: Bucket) => (
                    <Text strong key={key} className={`cvat-jobs-legend-${key}`} style={{ color }}>
                        {`• ${count} ${label} `}
                    </Text>
                ))}
                <Text strong type='secondary'>
                    {`• ${totalJobs} total`}
                </Text>
            </div>
            <div className='cvat-task-item-jobs-progress'>
                {buckets.map(({ key, label, count, color }: Bucket) => (
                    <div
                        key={key}
                        className={`cvat-task-item-jobs-progress-segment cvat-jobs-progress-${key}`}
                        style={{ flexGrow: count, backgroundColor: color }}
                        title={`${count} ${label}`}
                    />
                ))}
            </div>
        </>
    );
}

export default React.memo(TaskJobsProgress);
