// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './definitions.scss';

import React, { useEffect, useId, useState } from 'react';
import Tooltip from 'antd/lib/tooltip';

export type TermName = 'Session' | 'Working time' | 'Time per operation' | 'Model';

// Worded from GLOSSARY.md. Session inlines the session gap (five minutes); Time per operation inlines the idle
// pause (100 seconds).
export const DEFINITIONS: Record<TermName, string> = {
    Session: 'One uninterrupted interval of job work by one person, at most a day long. A pause longer than ' +
        'five minutes ends it. Seen for a single project, a session counts if it touched that project, and its ' +
        'length is only the time spent inside it.',
    'Working time': 'The time the server counts as worked, the same figure Grafana reports. It is the only ' +
        'total: every breakdown of time adds up to it.',
    'Time per operation': "The time from a person's previous action to the end of the operation, so that " +
        'finding, deciding and pointing are part of it. A pause longer than 100 seconds before an action belongs ' +
        'to no operation.',
    Model: 'Created without a person drawing it: saved by a technical account or produced by the built-in ' +
        'detector. Model boxes have counts but no time.',
};

interface Props {
    // the term whose definition is shown
    name: TermName;
    // the words on the page that carry it (default: the term's name)
    children?: React.ReactNode;
}

// Words of the overview that carry a definition: dotted underline, focusable, the definition in a tooltip on
// hover, on keyboard focus and on a tap; Escape hides it, wherever the focus is. The tooltip is rendered (hidden)
// from the start, outside any scrolling table, so that the words are described by it (aria-describedby) before it
// first opens.
export function Term({ name, children }: Props): JSX.Element {
    const id = `${useId()}-definition`;
    const [open, setOpen] = useState(false);
    // the hidden tooltip is rendered once the page is in the document (a portal cannot be rendered before)
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    // while the tooltip is open (by hover too, with the focus elsewhere), Escape anywhere hides it. The listener
    // runs in the capture phase, before a selector or modal that stops the key, and leaves the key to them (an
    // open selector or modal closes on the same press).
    useEffect(() => {
        if (!open) return undefined;
        const onKey = (event: KeyboardEvent): void => {
            if (event.key === 'Escape') setOpen(false);
        };
        document.addEventListener('keydown', onKey, true);
        return () => document.removeEventListener('keydown', onKey, true);
    }, [open]);
    return (
        <Tooltip
            title={DEFINITIONS[name]}
            trigger={['hover', 'focus']}
            open={open}
            onOpenChange={setOpen}
            id={id}
            forceRender={mounted}
            overlayClassName='cvat-team-analytics-term-tooltip'
        >
            {/* a button, so that keyboard users reach the definition and a tap shows it on a touch screen */}
            <button
                type='button'
                className='cvat-team-analytics-term'
                aria-describedby={id}
                onClick={() => setOpen(true)}
                onKeyDown={(event) => {
                    if (event.key === 'Escape' && open) {
                        event.stopPropagation();
                        setOpen(false);
                    }
                }}
            >
                {children ?? name}
            </button>
        </Tooltip>
    );
}
