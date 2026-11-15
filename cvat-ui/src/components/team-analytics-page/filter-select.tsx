// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, {
    useEffect, useId, useRef, useState,
} from 'react';
import { DownOutlined } from '@ant-design/icons';

import { FilterOption, FilterOptions } from './service';
import { arrange } from './full-view-list';

export interface FilterSelectProps {
    kind: 'project' | 'annotator';
    // "Project", "Annotator"
    label: string;
    // "All projects", "All annotators": the first option, which removes the filter
    allLabel: string;
    // what the button shows: the selected value's name, or `allLabel`
    value: string;
    selected: number | null;
    // the options of the period shown; asked each time the dropdown opens (the page keeps them in memory)
    load?: () => Promise<FilterOptions>;
    // the name an option is shown and searched by
    nameOf: (option: FilterOption) => string;
    // null: all
    onPick: (id: number | null) => void;
}

type Answer = { kind: 'loading' } | FilterOptions;

interface Item {
    id: number | null;
    name: string;
}

const STATUS: Record<Exclude<Answer['kind'], 'ready'>, string> = {
    loading: 'Loading…',
    withheld: 'This period is not processed yet',
    failed: 'Could not load the list',
};

// One filter of the filter row as a searchable single-select dropdown: a button naming the filter and its value
// opens a popup with a search field (the combobox) and the list of options (the listbox); the clear button
// beside it removes an active filter. Keyboard: Enter, Space or ArrowDown opens; arrows move; Enter picks;
// Escape closes and returns focus to the button. Clicking outside closes it.
export default function FilterSelect({
    kind, label, allLabel, value, selected, load, nameOf, onPick,
}: FilterSelectProps): JSX.Element {
    const id = useId();
    const listId = `${id}-options`;
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [answer, setAnswer] = useState<Answer>({ kind: 'loading' });
    const [active, setActive] = useState(0);
    const wrapper = useRef<HTMLDivElement>(null);
    const button = useRef<HTMLButtonElement>(null);
    const search = useRef<HTMLInputElement>(null);
    // the latest opening: an answer that arrives after another opening, or after closing, is dropped
    const opening = useRef(0);

    let rows: Item[] = answer.kind === 'ready' ? answer.options.map((option) => ({
        id: option.id, name: nameOf(option),
    })) : [];
    // a selected value that is not among the options (a shared link, a period without figures) stays offered
    if (selected !== null && !rows.some((row) => row.id === selected)) rows = [{ id: selected, name: value }, ...rows];
    const items: Item[] = [{ id: null, name: allLabel }, ...arrange(rows, query, 'value')];
    const activeIndex = Math.min(active, items.length - 1);

    let status: string | null = null;
    if (answer.kind !== 'ready') status = STATUS[answer.kind];
    else if (items.length === 1 && query.trim()) status = 'No match for this search';

    const close = (returnFocus: boolean): void => {
        opening.current += 1;
        setOpen(false);
        if (returnFocus) button.current?.focus();
    };

    const show = (): void => {
        opening.current += 1;
        const { current } = opening;
        setOpen(true);
        setQuery('');
        setActive(0);
        if (!load) {
            setAnswer({ kind: 'ready', options: [] });
            return;
        }
        setAnswer({ kind: 'loading' });
        load().then((next) => {
            if (opening.current === current) setAnswer(next);
        }, () => {
            if (opening.current === current) setAnswer({ kind: 'failed' });
        });
    };

    const pick = (item: Item): void => {
        // picking the selected value again keeps it (unlike a card row, which a second click clears)
        if (item.id !== selected) onPick(item.id);
        close(true);
    };

    // the search field takes focus on opening; the active option is placed on the selected one
    useEffect(() => {
        if (!open) return undefined;
        search.current?.focus();
        const onPointer = (event: MouseEvent): void => {
            if (wrapper.current && !wrapper.current.contains(event.target as Node)) close(false);
        };
        document.addEventListener('mousedown', onPointer);
        return () => document.removeEventListener('mousedown', onPointer);
    }, [open]);

    // on a new answer, the selected option becomes the active one
    useEffect(() => {
        if (!open) return;
        const index = items.findIndex((item) => item.id === selected);
        setActive(index < 0 ? 0 : index);
    }, [answer]);

    useEffect(() => {
        if (!open) return;
        const element = document.getElementById(`${id}-option-${activeIndex}`) as
            (HTMLElement & { scrollIntoView?: (options: object) => void }) | null;
        element?.scrollIntoView?.({ block: 'nearest' });
    }, [open, activeIndex]);

    const onButtonKey = (event: React.KeyboardEvent): void => {
        if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && !open) {
            event.preventDefault();
            show();
        }
    };

    const onSearchKey = (event: React.KeyboardEvent): void => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive(Math.min(activeIndex + 1, items.length - 1));
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive(Math.max(activeIndex - 1, 0));
        } else if (event.key === 'Enter') {
            event.preventDefault();
            pick(items[activeIndex]);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            close(true);
        } else if (event.key === 'Tab') {
            close(false);
        }
    };

    const plural = kind === 'project' ? 'projects' : 'annotators';
    return (
        <div
            ref={wrapper}
            className={`cvat-team-analytics-filter cvat-team-analytics-filter-${kind}${
                selected !== null ? ' cvat-team-analytics-filter-active' : ''}`}
        >
            <button
                ref={button}
                type='button'
                className='cvat-team-analytics-filter-button'
                title={value}
                aria-haspopup='listbox'
                aria-expanded={open}
                aria-controls={open ? listId : undefined}
                onClick={() => (open ? close(false) : show())}
                onKeyDown={onButtonKey}
            >
                <span className='cvat-team-analytics-filter-label'>{label}</span>
                <span className='cvat-team-analytics-filter-value'>{value}</span>
                <DownOutlined className='cvat-team-analytics-filter-arrow' aria-hidden />
            </button>
            {selected !== null ? (
                <button
                    type='button'
                    className='cvat-team-analytics-filter-clear'
                    aria-label={`Show all ${plural}`}
                    title={`Show all ${plural}`}
                    onClick={() => onPick(null)}
                >
                    ×
                </button>
            ) : null}
            {open ? (
                <div className='cvat-team-analytics-filter-popup'>
                    <input
                        ref={search}
                        className='cvat-team-analytics-filter-search'
                        type='text'
                        role='combobox'
                        aria-label={`Search ${plural}`}
                        aria-autocomplete='list'
                        aria-expanded
                        aria-controls={listId}
                        aria-activedescendant={`${id}-option-${activeIndex}`}
                        placeholder={`Search ${plural}`}
                        autoComplete='off'
                        spellCheck={false}
                        value={query}
                        onChange={(event) => {
                            setQuery(event.target.value);
                            setActive(0);
                        }}
                        onKeyDown={onSearchKey}
                    />
                    <ul id={listId} className='cvat-team-analytics-filter-options' role='listbox' aria-label={label}>
                        {items.map((item, index) => (
                            // keyboard selection goes through the search field (aria-activedescendant)
                            // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                            <li
                                key={item.id ?? 'all'}
                                id={`${id}-option-${index}`}
                                role='option'
                                aria-selected={item.id === selected}
                                className={`cvat-team-analytics-filter-option${
                                    index === activeIndex ? ' cvat-team-analytics-filter-option-active' : ''}${
                                    item.id === null ? ' cvat-team-analytics-filter-option-all' : ''}`}
                                title={item.name}
                                onMouseDown={(event) => event.preventDefault()}
                                onMouseEnter={() => setActive(index)}
                                onClick={() => pick(item)}
                            >
                                {item.name}
                            </li>
                        ))}
                    </ul>
                    <div className='cvat-team-analytics-filter-status' role='status'>{status}</div>
                </div>
            ) : null}
        </div>
    );
}
