// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { Job, JobStage, JobState } from 'cvat-core-wrapper';
import { TaskJobsSummary } from 'reducers';

export const TASK_JOB_COLORS: Record<JobStage, Record<JobState, string>> = {
    [JobStage.ANNOTATION]: {
        [JobState.NEW]: '#fafbb1',
        [JobState.IN_PROGRESS]: '#faad14',
        [JobState.COMPLETED]: '#fafe01',
        [JobState.REJECTED]: '#ff4136',
    },
    [JobStage.VALIDATION]: {
        [JobState.NEW]: '#b4dafd',
        [JobState.IN_PROGRESS]: '#1890ff',
        [JobState.COMPLETED]: '#00478a',
        [JobState.REJECTED]: '#ff4136',
    },
    [JobStage.ACCEPTANCE]: {
        [JobState.NEW]: '#b3ff66',
        [JobState.IN_PROGRESS]: '#b3ff66',
        [JobState.COMPLETED]: '#61c200',
        [JobState.REJECTED]: '#ff4136',
    },
};

function emptyStateCounts(): Record<JobState, number> {
    return {
        [JobState.NEW]: 0,
        [JobState.IN_PROGRESS]: 0,
        [JobState.COMPLETED]: 0,
        [JobState.REJECTED]: 0,
    };
}

function emptySummary(): TaskJobsSummary {
    return {
        counts: {
            [JobStage.ANNOTATION]: emptyStateCounts(),
            [JobStage.VALIDATION]: emptyStateCounts(),
            [JobStage.ACCEPTANCE]: emptyStateCounts(),
        },
        fetched: 0,
    };
}

export default function aggregateTaskJobs(jobs: Job[], taskIds: number[]): Record<number, TaskJobsSummary> {
    const summary: Record<number, TaskJobsSummary> = {};
    for (const taskId of taskIds) {
        summary[taskId] = emptySummary();
    }

    for (const job of jobs) {
        const taskSummary = job.taskId === null ? null : summary[job.taskId];
        if (taskSummary) {
            taskSummary.counts[job.stage][job.state] += 1;
            taskSummary.fetched += 1;
        }
    }

    return summary;
}
