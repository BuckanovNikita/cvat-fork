// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import '../creation-methods.scss';

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { CreationMethods, SavedBoxes } from '../service';
import {
    MISSING, formatCount, formatSeconds, formatShare,
} from '../format';
import { METHOD_NAMES, MODEL_COLOR, MODEL_NAME } from '../creation-methods';
import { OPERATION_LOOKS } from '../operations';
import { shapeWording } from '../shapes';
import { FullViewButton } from '../full-view-button';
import { Term } from '../definitions';

interface Props {
    methods: CreationMethods;
    // a legacy period: saved boxes are the one box figure it has
    legacy?: boolean;
    savedBoxes?: SavedBoxes;
    onFullView?: () => void;
}

// What Model is, next to its figure: 'Model: boxes saved by 2 technical accounts or made with the built-in
// detector. A re-upload by a technical account counts again.'
function modelNote(nouns: string, technicalAccounts: number): string {
    if (!technicalAccounts) return `Model: ${nouns} made with the built-in detector.`;
    const accounts = `${formatCount(technicalAccounts)} technical account${technicalAccounts === 1 ? '' : 's'}`;
    return `Model: ${nouns} saved by ${accounts} or made with the built-in detector. ` +
        'A re-upload by a technical account counts again.';
}

// How objects are created: drawn, pasted and propagated, each with a bar, its count, share and average time,
// then the three together with the Creation operation's average. Model, when the response has it, is a fourth
// row with a count and a share and no time, outside the three's total, with a note on what it counts.
function CreationMethodsCard({
    methods, legacy = false, savedBoxes, onFullView,
}: Props): JSX.Element {
    const { nouns } = shapeWording(methods);
    const { model } = methods;
    const largest = Math.max(1, ...methods.rows.map((row) => row.objects), model?.objects ?? 0);
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-creation-methods'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>{`How ${nouns.toLowerCase()} are created`}</Text>
                <FullViewButton onClick={onFullView} />
            </div>
            <Text type='secondary'>Each creation method counted on its own</Text>
            <div className='cvat-team-analytics-table-scroll'>
                <table className='cvat-team-analytics-table'>
                    <thead>
                        <tr>
                            <th>Method</th>
                            <th aria-hidden='true' />
                            <th>{nouns}</th>
                            <th>Share</th>
                            <th><Term name='Time per operation'>Avg time</Term></th>
                        </tr>
                    </thead>
                    <tbody>
                        {methods.rows.map((row) => {
                            const name = METHOD_NAMES[row.method];
                            return (
                                <tr key={row.method} className='cvat-team-analytics-method-row'>
                                    <td className='cvat-team-analytics-operation-name'>{name}</td>
                                    <td className='cvat-team-analytics-method-bar-cell'>
                                        <span
                                            className='cvat-team-analytics-method-bar'
                                            style={{
                                                width: `${(row.objects / largest) * 100}%`,
                                                background: OPERATION_LOOKS.creation.color,
                                            }}
                                        />
                                    </td>
                                    <td title={`${name}: ${formatCount(row.objects)} (${formatShare(row.share)})`}>
                                        {formatCount(row.objects)}
                                    </td>
                                    <td>{formatShare(row.share)}</td>
                                    <td>{formatSeconds(row.average_ms)}</td>
                                </tr>
                            );
                        })}
                        {model ? (
                            // the hover text sits on the count, not the row: it must not cover the Model definition
                            <tr className='cvat-team-analytics-method-row cvat-team-analytics-model-row'>
                                <td className='cvat-team-analytics-operation-name'>
                                    <Term name='Model'>{MODEL_NAME}</Term>
                                </td>
                                <td className='cvat-team-analytics-method-bar-cell'>
                                    <span
                                        className='cvat-team-analytics-method-bar'
                                        style={{
                                            width: `${(model.objects / largest) * 100}%`, background: MODEL_COLOR,
                                        }}
                                    />
                                </td>
                                <td
                                    title={`${MODEL_NAME}: ${formatCount(model.objects)} (${formatShare(model.share)})`}
                                >
                                    {formatCount(model.objects)}
                                </td>
                                <td>{formatShare(model.share)}</td>
                                <td>{MISSING}</td>
                            </tr>
                        ) : null}
                        <tr className='cvat-team-analytics-methods-total'>
                            <td colSpan={2}>All annotator methods</td>
                            <td>{formatCount(methods.total.objects)}</td>
                            <td />
                            <td>{formatSeconds(methods.total.average_ms)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {model ? (
                <Text type='secondary' className='cvat-team-analytics-methods-note'>
                    {modelNote(nouns.toLowerCase(), methods.technical_accounts ?? 0)}
                </Text>
            ) : null}
            {legacy && savedBoxes ? (
                <Text type='secondary' className='cvat-team-analytics-saved-boxes-note'>
                    {`${formatCount(savedBoxes.boxes)} single-frame boxes were saved in this period, ` +
                        'all methods together.'}
                </Text>
            ) : null}
        </section>
    );
}

export default React.memo(CreationMethodsCard);
