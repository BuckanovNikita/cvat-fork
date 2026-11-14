// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { OperationsFigures } from '../service';
import {
    MISSING, exactHours, formatCount, formatHours, formatSeconds, formatShare,
} from '../format';
import {
    InputSplit, OPERATION_LOOKS, inputSplit, isRecorded,
} from '../operations';
import { shapeWording } from '../shapes';
import { FullViewButton } from '../full-view-button';

interface Props {
    figures: OperationsFigures;
    onFullView?: () => void;
}

const HOTKEY_COLOR = '#2a78d6';
const MOUSE_COLOR = '#c9c8c2';

function InputSplitCell({ name, split }: { name: string; split: InputSplit }): JSX.Element {
    if (split.kind === 'split') {
        const hotkey = Math.round(split.hotkey * 100);
        const mouse = 100 - hotkey;
        return (
            <td
                className='cvat-team-analytics-input-split'
                title={`${name}: ${hotkey}% by hotkey, ${mouse}% by mouse`}
            >
                <span className='cvat-team-analytics-input-split-bar' aria-hidden>
                    <span style={{ flexGrow: Math.max(split.hotkey, 0.01), background: HOTKEY_COLOR }} />
                    <span style={{ flexGrow: Math.max(split.mouse, 0.01), background: MOUSE_COLOR }} />
                </span>
                {`${hotkey}% / ${mouse}%`}
            </td>
        );
    }
    const label = { 'mouse-only': 'Mouse only', 'not-recorded': 'Not recorded', none: MISSING }[split.kind];
    return <td className='cvat-team-analytics-input-split cvat-team-analytics-not-recorded'>{label}</td>;
}

// The four operations: objects, average time per object, total time and share of working time.
function OperationsTableCard({ figures, onFullView }: Props): JSX.Element {
    const rows = figures.rows.filter((row) => row.operation !== 'other');
    const wording = shapeWording(figures);
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-operations'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>{wording.operations}</Text>
                <FullViewButton onClick={onFullView} />
            </div>
            <Text type='secondary'>
                {`Counts and average time per ${wording.noun} · ${wording.label.toLowerCase()}`}
            </Text>
            <div className='cvat-team-analytics-table-scroll'>
                <table className='cvat-team-analytics-table'>
                    <thead>
                        <tr>
                            <th>Operation</th>
                            <th>{wording.nouns}</th>
                            <th>Avg time</th>
                            <th>Total time</th>
                            <th>Share</th>
                            <th>Started by hotkey / mouse</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => {
                            const look = OPERATION_LOOKS[row.operation];
                            const recorded = isRecorded(figures, row.operation);
                            return (
                                <tr key={row.operation}>
                                    <td>
                                        <span className='cvat-team-analytics-swatch' style={{ background: look.color }} />
                                        <span className='cvat-team-analytics-operation-name'>{look.name}</span>
                                    </td>
                                    {recorded ? (
                                        <>
                                            <td>{formatCount(row.objects)}</td>
                                            <td>{formatSeconds(row.average_ms)}</td>
                                            <td title={exactHours(row.time_ms)}>{formatHours(row.time_ms)}</td>
                                            <td>{formatShare(row.share)}</td>
                                        </>
                                    ) : (
                                        <>
                                            <td className='cvat-team-analytics-not-recorded'>Not recorded</td>
                                            <td>{MISSING}</td>
                                            <td>{MISSING}</td>
                                            <td>{MISSING}</td>
                                        </>
                                    )}
                                    <InputSplitCell name={look.name} split={inputSplit(figures, row)} />
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            <Text type='secondary' className='cvat-team-analytics-footnote'>
                Creation covers drawn, pasted and propagated objects. Alignment is done on the canvas, so it has no
                hotkey. Average time runs from the previous action to
                the end of the operation; pauses over 100 seconds are left out.
            </Text>
        </section>
    );
}

export default React.memo(OperationsTableCard);
