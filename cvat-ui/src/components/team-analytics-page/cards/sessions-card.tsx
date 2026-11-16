// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { SessionFigures } from '../service';
import { Term } from '../definitions';
import { exactHours, formatDuration } from '../format';

interface Props {
    figures: SessionFigures;
}

// Headline figure for the scope: the number of sessions and their average length.
function SessionsCard({ figures }: Props): JSX.Element {
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-sessions'>
            <Text type='secondary'><Term name='Session'>Sessions</Term></Text>
            {/* the hover text sits on the value, not the card, so that it never covers the Session definition */}
            <div
                className='cvat-team-analytics-headline-value'
                title={`Uninterrupted intervals of work · ${exactHours(figures.total_ms)} in total`}
            >
                {figures.sessions.toLocaleString('en-US')}
            </div>
            <Text type='secondary'>
                {figures.sessions > 0 ? `average ${formatDuration(figures.average_ms)}` : 'no sessions in this period'}
            </Text>
        </section>
    );
}

export default React.memo(SessionsCard);
