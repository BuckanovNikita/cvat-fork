// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './definitions.scss';

import React from 'react';

// Worded from GLOSSARY.md. Session inlines the session gap (five minutes); Time per operation inlines the idle
// pause (100 seconds).
const DEFINITIONS: [string, string][] = [
    ['Session', 'One uninterrupted interval of job work by one person, at most a day long. A pause longer than ' +
        'five minutes ends it. Seen for a single project, a session counts if it touched that project, and its ' +
        'length is only the time spent inside it.'],
    ['Working time', 'The time the server counts as worked, the same figure Grafana reports. It is the only ' +
        'total: every breakdown of time adds up to it.'],
    ['Time per operation', "The time from a person's previous action to the end of the operation, so that " +
        'finding, deciding and pointing are part of it. A pause longer than 100 seconds before an action belongs ' +
        'to no operation.'],
    ['Model', 'Created without a person drawing it: saved by a technical account or produced by the built-in ' +
        'detector. Model boxes have counts but no time.'],
];

// The short definitions that end the overview, so a figure can be checked without leaving the page.
export default function Definitions(): JSX.Element {
    return (
        <section className='cvat-team-analytics-definitions' aria-label='Definitions'>
            {DEFINITIONS.map(([term, definition]) => (
                <p key={term} className='cvat-team-analytics-definition'>
                    <span className='cvat-team-analytics-definition-term'>{`${term}.`}</span>
                    {` ${definition}`}
                </p>
            ))}
        </section>
    );
}
