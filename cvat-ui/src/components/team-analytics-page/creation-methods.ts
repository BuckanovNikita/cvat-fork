// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { CreationMethodName } from './service';

// Each creation method has one name everywhere on the page (GLOSSARY.md wording).
export const METHOD_NAMES: Record<CreationMethodName, string> = {
    drawn: 'Drawn',
    pasted: 'Pasted',
    propagated: 'Propagated',
};

// Model is the fourth method: counts only, in the colour of work no person did.
export const MODEL_NAME = 'Model';
export const MODEL_COLOR = '#c9c8c2';
