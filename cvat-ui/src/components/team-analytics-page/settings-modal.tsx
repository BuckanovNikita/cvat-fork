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
    SettingsUser, TechnicalAccount, loadSettings, requestService, requestSettings, saveSettings, searchUsers,
} from './service';

interface Props {
    open: boolean;
    onClose: () => void;
    // the list was saved: the page closes the screen and loads its figures again
    onSaved: () => void;
    // how long typing must pause before the users are searched
    searchDelayMs?: number;
}

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

// "Team Analytics settings": the Technical accounts list of the instance, edited here by an administrator and
// saved as a whole. A change applies to every past period the next time the page is loaded.
export default function SettingsModal({
    open, onClose, onSaved, searchDelayMs = 400,
}: Props): JSX.Element {
    const id = useId();
    const [loaded, setLoaded] = useState<Loaded>({ kind: 'loading' });
    const [accounts, setAccounts] = useState<TechnicalAccount[]>([]);
    const [users, setUsers] = useState<SettingsUser[]>([]);
    const [searching, setSearching] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    // the latest load and search: an answer to an older one is dropped
    const loads = useRef(0);
    const searches = useRef(0);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        setError(null);
        setSaving(false);
        setUsers([]);
        load();
        return () => {
            loads.current += 1;
            searches.current += 1;
            if (timer.current) clearTimeout(timer.current);
        };
    }, [open]);

    const search = (text: string): void => {
        if (timer.current) clearTimeout(timer.current);
        searches.current += 1;
        const { current } = searches;
        setSearching(true);
        timer.current = setTimeout(() => {
            searchUsers(text.trim(), requestService).then((found) => {
                if (searches.current !== current) return;
                setUsers(found ?? []);
                setSearching(false);
            });
        }, searchDelayMs);
    };

    const listed = new Set(accounts.map((account) => account.user_id));
    // accounts already on the list are not offered
    const offered = users.filter((user) => !listed.has(user.id));

    const add = (userId: number): void => {
        const user = users.find((candidate) => candidate.id === userId);
        if (!user || listed.has(userId)) return;
        setAccounts([...accounts, { user_id: user.id, user_name: user.username, deleted: false }]);
    };

    const save = (): void => {
        setSaving(true);
        setError(null);
        saveSettings(accounts.map((account) => account.user_id), requestSettings).then((result) => {
            setSaving(false);
            if (result.kind === 'saved') onSaved();
            else setError(result.error);
        });
    };

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
                    notFoundContent={searching ? 'Searching…' : 'No users found'}
                    options={offered.map((user) => ({ value: user.id, label: userLabel(user) }))}
                    onSearch={search}
                    onDropdownVisibleChange={(visible: boolean) => { if (visible) search(''); }}
                    onChange={(value: number | null) => { if (value !== null) add(value); }}
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
            onCancel={onClose}
            confirmLoading={saving}
            okButtonProps={{ disabled: loaded.kind !== 'ready', className: 'cvat-team-analytics-settings-save' }}
            cancelButtonProps={{ className: 'cvat-team-analytics-settings-cancel' }}
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
