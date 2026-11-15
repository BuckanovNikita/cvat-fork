// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

interface Props {
    // active annotators and their projects within the scope and both filters
    annotators: number;
    projects: number;
    // with an annotator selected: how many annotators the annotator chart lists in all
    of?: number | null;
    projectSelected: boolean;
}

// Headline figure: how many annotators were active in the scope and across how many projects.
function AnnotatorsCard({
    annotators, projects, of = null, projectSelected,
}: Props): JSX.Element {
    let hint = `across ${projects.toLocaleString('en-US')} ${projects === 1 ? 'project' : 'projects'}`;
    if (projectSelected) hint = 'worked in the selected project';
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-annotators'>
            <Text type='secondary'>Active annotators</Text>
            <div className='cvat-team-analytics-headline-value'>
                {of === null ? annotators.toLocaleString('en-US') : `${annotators} of ${of.toLocaleString('en-US')}`}
            </div>
            <Text type='secondary'>{hint}</Text>
        </section>
    );
}

export default React.memo(AnnotatorsCard);
