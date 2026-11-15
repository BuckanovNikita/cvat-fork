// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Result from 'antd/lib/result';

// Shown in place of the page when it fails to load or the service cannot be reached.
export default function TeamAnalyticsErrorPanel(): JSX.Element {
    return (
        <Result
            className='cvat-team-analytics-error'
            status='warning'
            title='Team analytics could not be loaded'
            subTitle='The analytics service did not answer. The rest of CVAT is not affected. Try again later.'
        />
    );
}
