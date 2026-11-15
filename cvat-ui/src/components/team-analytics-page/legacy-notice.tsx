// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

import { hasNoJobWork } from './operations';
import { OperationsFigures } from './service';

// Shown for a legacy period: it ends before the cutover to the new activity logging (the first shape-tagged
// event on the instance), so missing figures are not zeros.
export default function LegacyNotice(): JSX.Element {
    return (
        <div className='cvat-team-analytics-legacy-notice' role='note'>
            <div className='cvat-team-analytics-legacy-notice-title'>
                This period was recorded before the new activity logging
            </div>
            <div>
                Old events do not say which shape was edited, so operations and timing below cover all shapes.
                Class changes and hotkey use were not recorded and start from the day the new UI is deployed.
                Projects, sessions, working time and the number of boxes saved are complete.
            </div>
        </div>
    );
}

// The cutover's calendar day for the viewer, e.g. "2 November 2026".
export function cutoverDay(cutover: string, timeZone?: string): string {
    return new Date(cutover).toLocaleDateString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric', ...(timeZone ? { timeZone } : {}),
    });
}

// Shown for a partly legacy period: the cutover falls inside it, so some figures cover only the part after it.
export function PartlyLegacyNotice({ cutover, timeZone }: { cutover: string; timeZone?: string }): JSX.Element {
    return (
        <div className='cvat-team-analytics-legacy-notice cvat-team-analytics-partly-legacy-notice' role='note'>
            <div className='cvat-team-analytics-legacy-notice-title'>
                {`The new activity logging started on ${cutoverDay(cutover, timeZone)}`}
            </div>
            <div>
                Bounding box figures, class changes and hotkey use cover only the days since; under All shapes
                the operations before it are counted too. Projects, sessions, working time and the number of
                boxes saved cover the whole period.
            </div>
        </div>
    );
}

// The notice the shown period needs: legacy, partly legacy (naming the cutover day), or none. A period with no
// job work in the scope shows only the empty state, so neither notice.
export function LegacyNotices({ operations, timeZone }: {
    operations?: OperationsFigures;
    timeZone?: string;
}): JSX.Element | null {
    if (!operations || hasNoJobWork(operations)) return null;
    if (operations.legacy) return <LegacyNotice />;
    if (operations.partly_legacy && operations.cutover) {
        return <PartlyLegacyNotice cutover={operations.cutover} timeZone={timeZone} />;
    }
    return null;
}
