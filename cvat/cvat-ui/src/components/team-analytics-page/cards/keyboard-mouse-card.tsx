// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import '../keyboard-mouse.scss';
import React from 'react';
import Text from 'antd/lib/typography/Text';

import { InputFigures } from '../service';
import { formatCount, formatShare, shortCount } from '../format';
import { HotkeyLabels, hotkeyLabel } from '../hotkeys';
import { FullViewButton, ShowAllButton } from '../full-view-button';

interface Props {
    // null: the service sent no keyboard figures
    figures: InputFigures | null;
    // a legacy period (no shape-tagged operation): hotkey use was not recorded unless input was counted
    legacy: boolean;
    labels?: HotkeyLabels;
    // opens the full view of every hotkey (offered while hotkey use is recorded)
    onFullView?: () => void;
}

const HOTKEY_COLOR = '#2a78d6';

function Figure({ label, value, title }: { label: string; value: string; title?: string }): JSX.Element {
    return (
        <div className='cvat-team-analytics-keyboard-figure' title={title}>
            <Text type='secondary'>{label}</Text>
            <div className='cvat-team-analytics-keyboard-value'>{value}</div>
        </div>
    );
}

// Hotkey actions against mouse actions, the hotkey share and the most used hotkeys of the scope.
function KeyboardMouseCard({
    figures, legacy, labels, onFullView,
}: Props): JSX.Element {
    let body: JSX.Element;
    // a scope without shape-tagged operations after deployment (navigation or review only) still has
    // recorded input: only a legacy period with nothing counted says it was not recorded
    const counted = !!figures && figures.hotkey_actions + figures.mouse_actions + figures.canvas_clicks > 0;
    const recorded = !(!figures || (legacy && !counted));
    if (!figures || !recorded) {
        body = (
            <div className='cvat-team-analytics-keyboard-not-recorded'>
                <Text strong>Hotkey use was not recorded in this period</Text>
                <Text type='secondary'>
                    Hotkey and mouse use is recorded from the day the new UI is deployed. Pick a later period to see it.
                </Text>
            </div>
        );
    } else {
        const all = figures.hotkey_actions + figures.mouse_actions;
        const most = Math.max(1, ...figures.top_hotkeys.map((row) => row.actions));
        body = (
            <div className='cvat-team-analytics-keyboard-body'>
                <div className='cvat-team-analytics-keyboard-totals'>
                    <div className='cvat-team-analytics-keyboard-figures'>
                        <Figure
                            label='Hotkey actions'
                            value={shortCount(figures.hotkey_actions)}
                            title={`${formatCount(figures.hotkey_actions)} exactly`}
                        />
                        <Figure
                            label='Mouse actions'
                            value={shortCount(figures.mouse_actions)}
                            title={`${formatCount(figures.mouse_actions)} exactly`}
                        />
                        <Figure label='Hotkey share' value={formatShare(figures.hotkey_share)} />
                    </div>
                    <div
                        className='cvat-team-analytics-keyboard-share'
                        title={`${formatCount(figures.hotkey_actions)} hotkey actions of ${formatCount(all)}`}
                    >
                        <div style={{ width: `${Math.round((figures.hotkey_share ?? 0) * 1000) / 10}%` }} />
                    </div>
                    <Text type='secondary'>
                        A mouse action is a click on a button, menu or sidebar control. Clicks on the canvas itself
                        are drawing and editing, so they are not compared with hotkeys.
                    </Text>
                </div>
                <div className='cvat-team-analytics-keyboard-top'>
                    <Text strong>Most used hotkeys</Text>
                    {figures.top_hotkeys.length ? (
                        <ul className='cvat-team-analytics-hotkeys'>
                            {figures.top_hotkeys.map((row) => {
                                const label = hotkeyLabel(row.action, labels);
                                return (
                                    <li
                                        key={row.action}
                                        className='cvat-team-analytics-hotkey-row'
                                        title={`${label.name} (${label.keys}): ${formatCount(row.actions)}`}
                                    >
                                        <span className='cvat-team-analytics-hotkey-name'>{label.name}</span>
                                        {' '}
                                        <kbd className='cvat-team-analytics-hotkey-keys'>{label.keys}</kbd>
                                        {' '}
                                        <span className='cvat-team-analytics-hotkey-bar'>
                                            <span
                                                style={{
                                                    width: `${Math.max(0.5, (row.actions / most) * 100)}%`,
                                                    background: HOTKEY_COLOR,
                                                }}
                                            />
                                        </span>
                                        <span className='cvat-team-analytics-hotkey-value'>{formatCount(row.actions)}</span>
                                    </li>
                                );
                            })}
                        </ul>
                    ) : (
                        <Text type='secondary' className='cvat-team-analytics-hotkeys-none'>
                            No hotkey actions in this period
                        </Text>
                    )}
                    {figures.rest.count > 0 ? (
                        <div className='cvat-team-analytics-hotkeys-rest'>
                            <span>{`${formatCount(figures.rest.count)} other hotkeys, not shown`}</span>
                            {' '}
                            <span>{formatCount(figures.rest.actions)}</span>
                        </div>
                    ) : null}
                    {figures.rest.count > 0 ? (
                        <ShowAllButton count={figures.top_hotkeys.length + figures.rest.count} onClick={onFullView} />
                    ) : null}
                </div>
            </div>
        );
    }
    return (
        <section className='cvat-team-analytics-card cvat-team-analytics-keyboard'>
            <div className='cvat-team-analytics-card-header'>
                <Text strong>Keyboard and mouse</Text>
                {recorded ? <FullViewButton onClick={onFullView} /> : null}
            </div>
            <Text type='secondary'>Hotkey actions against mouse actions on controls</Text>
            {body}
        </section>
    );
}

export default React.memo(KeyboardMouseCard);
