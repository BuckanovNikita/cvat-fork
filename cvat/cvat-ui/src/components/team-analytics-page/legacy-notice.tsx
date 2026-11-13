// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

// Shown for a legacy period: the scope has no shape-tagged event in it, so missing figures are not zeros.
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
