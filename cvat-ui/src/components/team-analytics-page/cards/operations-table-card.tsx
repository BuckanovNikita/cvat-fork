// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import '../operations.scss';

import React, { useId } from 'react';
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
import { Term } from '../definitions';

interface Props {
    figures: OperationsFigures;
    onFullView?: () => void;
}

const HOTKEY_COLOR = '#2a78d6';
const MOUSE_COLOR = '#c9c8c2';

// The second row of an operation: how its objects were started, across the whole table width. `headers` ties
// it to the operation's row header, and a hidden prefix names the operation for a screen reader that reads the
// row on its own.
function InputSplitRow({ name, split, header }: { name: string; split: InputSplit; header: string }): JSX.Element {
    const prefix = <span className='cvat-team-analytics-visually-hidden'>{`${name} started by: `}</span>;
    if (split.kind === 'split') {
        const hotkey = Math.round(split.hotkey * 100);
        const mouse = 100 - hotkey;
        return (
            <tr className='cvat-team-analytics-input-split-row'>
                <td
                    colSpan={5}
                    headers={header}
                    className='cvat-team-analytics-input-split'
                    title={`${name}: ${hotkey}% by hotkey, ${mouse}% by mouse`}
                >
                    {prefix}
                    <span className='cvat-team-analytics-input-split-bar' aria-hidden>
                        <span style={{ flexGrow: Math.max(split.hotkey, 0.01), background: HOTKEY_COLOR }} />
                        <span style={{ flexGrow: Math.max(split.mouse, 0.01), background: MOUSE_COLOR }} />
                    </span>
                    {`${hotkey}% hotkey / ${mouse}% mouse`}
                </td>
            </tr>
        );
    }
    const label = { 'mouse-only': 'Mouse only', 'not-recorded': 'Not recorded', none: MISSING }[split.kind];
    return (
        <tr className='cvat-team-analytics-input-split-row'>
            <td
                colSpan={5}
                headers={header}
                className='cvat-team-analytics-input-split cvat-team-analytics-not-recorded'
            >
                {prefix}
                {label}
            </td>
        </tr>
    );
}

// The four operations: objects, average time per object, total time and share of working time, each with how
// its objects were started (hotkey or mouse) on a row of its own below, so that the table fits a narrow card.
function OperationsTableCard({ figures, onFullView }: Props): JSX.Element {
    const rows = figures.rows.filter((row) => row.operation !== 'other');
    const wording = shapeWording(figures);
    const idPrefix = useId();
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-operations'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>{wording.operations}</Text>
                <FullViewButton onClick={onFullView} />
            </div>
            <Text type='secondary'>
                {`Counts and average time per ${wording.noun} · ${wording.label.toLowerCase()}`}
            </Text>
            <div className='cvat-team-analytics-table-scroll cvat-team-analytics-operations-scroll'>
                <table className='cvat-team-analytics-operations-table'>
                    <thead>
                        <tr>
                            <th scope='col'>Operation</th>
                            <th scope='col'>{wording.nouns}</th>
                            <th scope='col'><Term name='Time per operation'>Avg time</Term></th>
                            <th scope='col'>Total time</th>
                            <th scope='col'>Share</th>
                        </tr>
                    </thead>
                    {rows.map((row) => {
                        const look = OPERATION_LOOKS[row.operation];
                        const recorded = isRecorded(figures, row.operation);
                        const header = `${idPrefix}-${row.operation}`;
                        // one group per operation: its figures and, below them, how its objects were started
                        return (
                            <tbody key={row.operation} className='cvat-team-analytics-operation-group'>
                                <tr className='cvat-team-analytics-operation-row'>
                                    <th scope='row' id={header}>
                                        <span className='cvat-team-analytics-swatch' style={{ background: look.color }} />
                                        <span className='cvat-team-analytics-operation-name'>{look.name}</span>
                                    </th>
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
                                </tr>
                                <InputSplitRow name={look.name} split={inputSplit(figures, row)} header={header} />
                            </tbody>
                        );
                    })}
                </table>
            </div>
            <Text type='secondary' className='cvat-team-analytics-footnote'>
                Creation covers drawn, pasted and propagated objects. The bar under each operation shows how its
                objects were started, by hotkey or by mouse; alignment is done on the canvas, so it has no hotkey.
                Average time runs from the previous action to the end of the operation; pauses over 100 seconds are
                left out.
            </Text>
        </section>
    );
}

export default React.memo(OperationsTableCard);
