// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './settings.scss';

import React, {
    useEffect, useId, useRef, useState,
} from 'react';
import Modal from 'antd/lib/modal';
import Select from 'antd/lib/select';
import Button from 'antd/lib/button';
import Spin from 'antd/lib/spin';
import { CloseOutlined } from '@ant-design/icons';

import {
    SAVE_UNFINISHED, SettingsUser, TechnicalAccount, loadSettings, requestService, requestSettings, saveSettings,
    searchUsers,
} from './service';

interface Props {
    open: boolean;
    onClose: () => void;
    // the list was saved: the page closes the screen and loads its figures again
    onSaved: () => void;
    // how long typing must pause before the users are searched
    searchDelayMs?: number;
    // how long a save is waited for (SAVE_TIME_LIMIT_MS)
    saveTimeLimitMs?: number;
}

// A save is waited for this long, then the modal stops waiting: it says the save did not finish and can be closed
// again. The server's own save takes a few milliseconds; the limit only ends a request that never answers (no
// timeout is set on it), which would otherwise keep the modal, and its mask over the page, open for good.
export const SAVE_TIME_LIMIT_MS = 30000;

type Loaded = { kind: 'loading' } | { kind: 'failed' } | { kind: 'ready' };

// Worded from GLOSSARY.md (Technical account)
const TECHNICAL_ACCOUNT = 'A technical account is a user account that stands for an automated process rather than ' +
    'a person. It is never listed among people, and every box it saves counts as a Model box.';

export function accountLabel(account: TechnicalAccount): string {
    return account.deleted ? `deleted account, id ${account.user_id}` : account.user_name;
}

function userLabel(user: SettingsUser): string {
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ');
    return name ? `${user.username} (${name})` : user.username;
}

// The server refuses a longer search (400)
export const SEARCH_MAX_LENGTH = 150;

// "Team Analytics settings": the Technical accounts list of the instance, edited here by an administrator and
// saved as a whole. A change applies to every past period the next time the page is loaded.
export default function SettingsModal({
    open, onClose, onSaved, searchDelayMs = 400, saveTimeLimitMs = SAVE_TIME_LIMIT_MS,
}: Props): JSX.Element {
    const id = useId();
    const [loaded, setLoaded] = useState<Loaded>({ kind: 'loading' });
    const [accounts, setAccounts] = useState<TechnicalAccount[]>([]);
    const [users, setUsers] = useState<SettingsUser[]>([]);
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [searchFailed, setSearchFailed] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    // the latest load and search: an answer to an older one is dropped
    const loads = useRef(0);
    const searches = useRef(0);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    // a save is on its way: no second save, and the modal does not close until it is answered or its time is up
    const inFlight = useRef(false);
    // the latest save and its time limit: an answer to a save no longer waited for is dropped
    const saves = useRef(0);
    const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    // the text typed so far, for the search that opening the list starts (typing into the closed picker opens it
    // too, and that search must not replace the typed one with an empty one)
    const typedText = useRef('');

    const load = (): void => {
        loads.current += 1;
        const { current } = loads;
        setLoaded({ kind: 'loading' });
        loadSettings(requestSettings).then((settings) => {
            if (loads.current !== current) return;
            if (!settings) {
                setLoaded({ kind: 'failed' });
                return;
            }
            setAccounts(settings.technical_accounts);
            setLoaded({ kind: 'ready' });
        });
    };

    useEffect(() => {
        if (!open) return undefined;
        inFlight.current = false;
        setError(null);
        setSaving(false);
        setUsers([]);
        typedText.current = '';
        setQuery('');
        setSearchFailed(false);
        load();
        return () => {
            // a save of this opening is no longer waited for
            loads.current += 1;
            searches.current += 1;
            saves.current += 1;
            if (timer.current) clearTimeout(timer.current);
            if (saveTimer.current) clearTimeout(saveTimer.current);
        };
    }, [open]);

    const search = (typed: string): void => {
        const text = typed.slice(0, SEARCH_MAX_LENGTH);
        typedText.current = text;
        setQuery(text);
        if (timer.current) clearTimeout(timer.current);
        searches.current += 1;
        const { current } = searches;
        setSearching(true);
        timer.current = setTimeout(() => {
            searchUsers(text.trim(), requestService).then((found) => {
                if (searches.current !== current) return;
                setUsers(found ?? []);
                setSearchFailed(found === null);
                setSearching(false);
            });
        }, searchDelayMs);
    };

    // the search answers at most 20 users, accounts already on the list among them: those are shown, marked and
    // not offered, so that the answer does not look shorter than it is
    const listed = new Set(accounts.map((account) => account.user_id));

    const add = (userId: number): void => {
        const user = users.find((candidate) => candidate.id === userId);
        if (!user || listed.has(userId)) return;
        setAccounts([...accounts, { user_id: user.id, user_name: user.username, deleted: false }]);
    };

    const save = (): void => {
        // the modal's own guard: a second Save (a double click, Enter) does not send a second list
        if (inFlight.current) return;
        inFlight.current = true;
        saves.current += 1;
        const { current } = saves;
        const stopWaiting = (): void => {
            inFlight.current = false;
            setSaving(false);
            if (saveTimer.current) clearTimeout(saveTimer.current);
            saveTimer.current = null;
        };
        setSaving(true);
        setError(null);
        // past the limit the save is no longer waited for: its answer, if it ever comes, is dropped (a save that
        // went through shows in the list the next time the settings are opened)
        saveTimer.current = setTimeout(() => {
            if (saves.current !== current) return;
            saves.current += 1;
            stopWaiting();
            setError(SAVE_UNFINISHED);
        }, saveTimeLimitMs);
        saveSettings(accounts.map((account) => account.user_id), requestSettings).then((result) => {
            // an answer for a save no longer waited for (its time was up, or the modal was closed by a refusal
            // meanwhile, and maybe opened again) changes nothing here
            if (saves.current !== current) return;
            stopWaiting();
            if (result.kind === 'saved') onSaved();
            else setError(result.error);
        });
    };

    // Cancel, the close button, Escape and the mask do nothing while a save is on its way
    const cancel = (): void => {
        if (!inFlight.current) onClose();
    };

    let notFound = 'No users found';
    if (searching) notFound = 'Searching…';
    else if (searchFailed) notFound = 'The search could not be completed.';

    let body: JSX.Element;
    if (loaded.kind === 'loading') {
        body = (
            <div className='cvat-team-analytics-settings-loading' role='status'>
                <Spin size='small' />
                <span>Loading…</span>
            </div>
        );
    } else if (loaded.kind === 'failed') {
        body = (
            <div className='cvat-team-analytics-settings-load-failed' role='alert'>
                <span>The settings could not be loaded.</span>
                <Button size='small' onClick={load}>Try again</Button>
            </div>
        );
    } else {
        body = (
            <>
                {accounts.length ? (
                    <ul className='cvat-team-analytics-settings-accounts' aria-labelledby={`${id}-title`}>
                        {accounts.map((account) => (
                            <li
                                key={account.user_id}
                                className={`cvat-team-analytics-settings-account${
                                    account.deleted ? ' cvat-team-analytics-settings-account-deleted' : ''}`}
                            >
                                <span className='cvat-team-analytics-settings-account-name'>
                                    {accountLabel(account)}
                                </span>
                                <Button
                                    type='text'
                                    size='small'
                                    className='cvat-team-analytics-settings-remove'
                                    aria-label={`Remove ${accountLabel(account)}`}
                                    title='Remove from the list'
                                    icon={<CloseOutlined />}
                                    onClick={() => setAccounts(
                                        accounts.filter((other) => other.user_id !== account.user_id),
                                    )}
                                />
                            </li>
                        ))}
                    </ul>
                ) : (
                    <div className='cvat-team-analytics-settings-empty'>No technical accounts.</div>
                )}
                {/* antd's Select puts `id` on its search input, the control this label names */}
                {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                <label className='cvat-team-analytics-settings-picker-label' htmlFor={`${id}-picker`}>
                    Add an account
                </label>
                <Select
                    id={`${id}-picker`}
                    className='cvat-team-analytics-settings-picker'
                    popupClassName='cvat-team-analytics-settings-picker-dropdown'
                    showSearch
                    filterOption={false}
                    virtual={false}
                    placeholder='Search users by name'
                    value={null}
                    loading={searching}
                    searchValue={query}
                    notFoundContent={(
                        <span
                            className={`cvat-team-analytics-settings-search-status${
                                searchFailed && !searching ? ' cvat-team-analytics-settings-search-failed' : ''}`}
                        >
                            {notFound}
                        </span>
                    )}
                    options={(searchFailed ? [] : users).map((user) => ({
                        value: user.id,
                        disabled: listed.has(user.id),
                        label: listed.has(user.id) ? (
                            <>
                                {userLabel(user)}
                                {' '}
                                <span className='cvat-team-analytics-settings-listed'>already on the list</span>
                            </>
                        ) : userLabel(user),
                    }))}
                    onSearch={search}
                    onDropdownVisibleChange={(visible: boolean) => { if (visible) search(typedText.current); }}
                    onChange={(value: number | null) => {
                        if (value !== null) add(value);
                        typedText.current = '';
                        setQuery('');
                    }}
                />
            </>
        );
    }

    return (
        <Modal
            className='cvat-team-analytics-settings-modal'
            title='Team Analytics settings'
            open={open}
            okText='Save'
            onOk={save}
            onCancel={cancel}
            confirmLoading={saving}
            maskClosable={!saving}
            keyboard={!saving}
            okButtonProps={{ disabled: loaded.kind !== 'ready', className: 'cvat-team-analytics-settings-save' }}
            cancelButtonProps={{ disabled: saving, className: 'cvat-team-analytics-settings-cancel' }}
            destroyOnClose
        >
            <section className='cvat-team-analytics-settings-section' aria-labelledby={`${id}-title`}>
                <h3 id={`${id}-title`} className='cvat-team-analytics-settings-title'>Technical accounts</h3>
                <p className='cvat-team-analytics-settings-text'>{TECHNICAL_ACCOUNT}</p>
                {body}
                <p className='cvat-team-analytics-settings-text cvat-team-analytics-settings-applies'>
                    A change applies to every past period the next time the page is loaded.
                </p>
                {error ? (
                    <div className='cvat-team-analytics-settings-error' role='alert'>{error}</div>
                ) : null}
            </section>
        </Modal>
    );
}
