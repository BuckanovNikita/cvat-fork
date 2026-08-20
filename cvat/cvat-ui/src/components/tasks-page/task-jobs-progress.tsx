// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';
import { TaskJobsSummary } from 'reducers';

interface Props {
    summary: TaskJobsSummary;
    totalJobs: number;
}

interface Bucket {
    key: string;
    label: string;
    count: number;
}

function TaskJobsProgress(props: Props): JSX.Element {
    const { summary, totalJobs } = props;

    // A user may have access to a subset of the task jobs only,
    // the rest is still displayed to keep the widget consistent with the total counter
    const inaccessibleJobs = Math.max(0, totalJobs - summary.fetched);
    const buckets: Bucket[] = [
        { key: 'annotation-new', label: 'not started', count: summary.annotationNew },
        { key: 'annotating', label: 'annotating', count: summary.annotating },
        { key: 'validation', label: 'on review', count: summary.validation },
        { key: 'acceptance', label: 'accepted', count: summary.acceptance },
        { key: 'rejected', label: 'rejected', count: summary.rejected },
        { key: 'inaccessible', label: 'not available', count: inaccessibleJobs },
    ].filter((bucket: Bucket) => bucket.count > 0);

    return (
        <>
            <div>
                {buckets.map(({ key, label, count }: Bucket) => (
                    <Text strong key={key} className={`cvat-jobs-legend-${key}`}>
                        {`• ${count} ${label} `}
                    </Text>
                ))}
                <Text strong type='secondary'>
                    {`• ${totalJobs} total`}
                </Text>
            </div>
            <div className='cvat-task-item-jobs-progress'>
                {buckets.map(({ key, label, count }: Bucket) => (
                    <div
                        key={key}
                        className={`cvat-task-item-jobs-progress-segment cvat-jobs-progress-${key}`}
                        style={{ flexGrow: count }}
                        title={`${count} ${label}`}
                    />
                ))}
            </div>
        </>
    );
}

export default React.memo(TaskJobsProgress);
