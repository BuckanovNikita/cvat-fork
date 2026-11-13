// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// The one place that supplies `input_method` to the operation and alignment fields (owned by ticket 13,
// keyboard and mouse). Until then no input method is recorded: the field is left out.

import { InputMethod, PAYLOAD } from './contract';

export type ActionKind = 'operation' | 'alignment';

// The input method that started the action being logged, or null when it is not known.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function currentInputMethod(kind: ActionKind): InputMethod | null {
    return null;
}

export function inputMethodFields(kind: ActionKind): Record<string, string> {
    const method = currentInputMethod(kind);
    return method ? { [PAYLOAD.inputMethod]: method } : {};
}
