// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';

// The Full view button in a chart's header; nothing without a handler (the page shown without an address).
export function FullViewButton({ onClick }: { onClick?: () => void }): JSX.Element | null {
    if (!onClick) return null;
    return (
        <button type='button' className='cvat-team-analytics-full-view-button' title='Full view' onClick={onClick}>
            <svg aria-hidden width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2'>
                <path d='M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5' />
            </svg>
            Full view
        </button>
    );
}

// A chart's "show all" control: opens its full view (a card on the overview never grows).
export function ShowAllButton({ count, onClick }: { count: number; onClick?: () => void }): JSX.Element | null {
    if (!onClick) return null;
    return (
        <button type='button' className='cvat-team-analytics-show-all' onClick={onClick}>
            {`Show all ${count.toLocaleString('en-US')} in full view`}
        </button>
    );
}
