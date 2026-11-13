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
