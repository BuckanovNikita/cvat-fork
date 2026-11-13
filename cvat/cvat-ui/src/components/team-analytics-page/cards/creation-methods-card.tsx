// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import '../creation-methods.scss';

import React from 'react';
import Text from 'antd/lib/typography/Text';

import { CreationMethods } from '../service';
import { formatCount, formatSeconds, formatShare } from '../format';
import { METHOD_NAMES } from '../creation-methods';
import { OPERATION_LOOKS } from '../operations';
import { shapeWording } from '../shapes';

interface Props {
    methods: CreationMethods;
}

// How objects are created: drawn, pasted and propagated, each with a bar, its count, share and average time,
// then the three together with the Creation operation's average.
function CreationMethodsCard({ methods }: Props): JSX.Element {
    const { nouns } = shapeWording(methods);
    const largest = Math.max(1, ...methods.rows.map((row) => row.objects));
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-creation-methods'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>{`How ${nouns.toLowerCase()} are created`}</Text>
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
                            <th>Avg time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {methods.rows.map((row) => {
                            const name = METHOD_NAMES[row.method];
                            return (
                                <tr
                                    key={row.method}
                                    className='cvat-team-analytics-method-row'
                                    title={`${name}: ${formatCount(row.objects)} (${formatShare(row.share)})`}
                                >
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
                                    <td>{formatCount(row.objects)}</td>
                                    <td>{formatShare(row.share)}</td>
                                    <td>{formatSeconds(row.average_ms)}</td>
                                </tr>
                            );
                        })}
                        <tr className='cvat-team-analytics-methods-total'>
                            <td colSpan={2}>All annotator methods</td>
                            <td>{formatCount(methods.total.objects)}</td>
                            <td />
                            <td>{formatSeconds(methods.total.average_ms)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>
    );
}

export default React.memo(CreationMethodsCard);
