// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { Job, JobStage, JobState } from 'cvat-core-wrapper';
import { TaskJobsSummary } from 'reducers';

function emptySummary(): TaskJobsSummary {
    return {
        annotationNew: 0,
        annotating: 0,
        validation: 0,
        acceptance: 0,
        rejected: 0,
        fetched: 0,
    };
}

// A rejected job is reported as rejected no matter which stage it is currently in
function bucketOf(job: Job): keyof Omit<TaskJobsSummary, 'fetched'> {
    if (job.state === JobState.REJECTED) {
        return 'rejected';
    }

    if (job.stage === JobStage.VALIDATION) {
        return 'validation';
    }

    if (job.stage === JobStage.ACCEPTANCE) {
        return 'acceptance';
    }

    return job.state === JobState.NEW ? 'annotationNew' : 'annotating';
}

export default function aggregateTaskJobs(jobs: Job[], taskIds: number[]): Record<number, TaskJobsSummary> {
    const summary: Record<number, TaskJobsSummary> = {};
    for (const taskId of taskIds) {
        summary[taskId] = emptySummary();
    }

    for (const job of jobs) {
        const taskSummary = job.taskId === null ? null : summary[job.taskId];
        if (taskSummary) {
            taskSummary[bucketOf(job)] += 1;
            taskSummary.fetched += 1;
        }
    }

    return summary;
}
