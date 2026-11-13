// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The service names hotkeys by action (what the shortcut does). The page labels them with the viewer's
// own keymap at view time: the action's name and the keys it is bound to now.

import { MISSING } from './format';

export interface HotkeyLabel {
    name: string;
    keys: string;
}

// action -> label
export type HotkeyLabels = Record<string, HotkeyLabel>;

interface KeyMapLike {
    keyMap?: Record<string, { name?: string } | undefined>;
    normalizedKeyMap?: Record<string, string | undefined>;
}

/** Labels from the shortcuts store (keyMap: names; normalizedKeyMap: display keys such as "[Ctrl+S]"). */
export function hotkeyLabels(shortcuts: KeyMapLike | null | undefined): HotkeyLabels {
    const labels: HotkeyLabels = {};
    const keyMap = shortcuts?.keyMap ?? {};
    const normalized = shortcuts?.normalizedKeyMap ?? {};
    for (const [action, item] of Object.entries(keyMap)) {
        if (!item?.name) continue;
        const keys = (normalized[action] ?? '').replace(/^\[(.*)\]$/, '$1');
        labels[action] = { name: item.name, keys: keys || MISSING };
    }
    return labels;
}

/** The label of `action`; an action the viewer's keymap does not know is shown by its name. */
export function hotkeyLabel(action: string, labels: HotkeyLabels | undefined): HotkeyLabel {
    return labels?.[action] ?? { name: action, keys: MISSING };
}
