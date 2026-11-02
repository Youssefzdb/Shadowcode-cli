/** Tool-card state machine for the Shadowcode Ink TUI.
 *
 * HONEST LIMIT, documented here and in the report: the Python
 * core's JSON-lines protocol emits a `tool` event only AFTER a
 * tool finishes (shadowcode_pkg/agent.py calls on_tool with the
 * result). There is no tool-start event, so the TUI cannot
 * honestly show a *named* tool as running before its result
 * arrives. What it can show, truthfully:
 *   - a generic "working…" indicator while a turn is running
 *     (the App's thinking state), and
 *   - a card per real `tool` event, with its real result and a
 *     done/failed status derived from that result.
 * The state machine below models running -> done/failed for
 * when a start event exists (and for tests); the App feeds it
 * a start+complete pair per real event, with elapsed measured
 * between turn start / previous tool completion and this
 * event — i.e. turn-segment elapsed, NOT core execution time,
 * which the core does not report.
 */

import { toolStatusMark, truncate } from './protocol.js';

export type ToolCardStatus = 'running' | 'done' | 'failed';

export interface ToolCard {
	id: number;
	name: string;
	status: ToolCardStatus;
	startedAt: number;
	completedAt?: number;
	elapsedMs?: number;
	result: string;
}

let nextId = 1;

export function startTool(cards: ToolCard[], name: string, now = Date.now()): ToolCard[] {
	return [...cards, { id: nextId++, name, status: 'running', startedAt: now, result: '' }];
}

export function completeTool(
	cards: ToolCard[],
	name: string,
	result: string,
	now = Date.now(),
): ToolCard[] {
	let done = false;
	const out = cards.map((card) => {
		if (!done && card.name === name && card.status === 'running') {
			done = true;
			return {
				...card,
				status: (toolStatusMark(result) === '✕' ? 'failed' : 'done') as ToolCardStatus,
				completedAt: now,
				elapsedMs: now - card.startedAt,
				result,
			};
		}
		return card;
	});
	return done ? out : cards;
}

/** One completed card from a single real tool event. */
export function cardFromToolEvent(name: string, result: string, startedAt: number, now = Date.now()): ToolCard {
	return completeTool(startTool([], name, startedAt), name, result, now)[0] as ToolCard;
}

export function formatElapsed(ms?: number): string {
	if (ms === undefined) return '';
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(1)}s`;
}

export function cardPreview(card: ToolCard): string {
	return truncate(card.result.replace(/\n/g, ' '), 100);
}

/** Human title for a tool card, from the real tool name + result.
 *
 * The core protocol carries no tool arguments, only the result
 * string, so a target is shown ONLY when the result itself
 * names a file ("wrote <path> (…)", "edited <path>",
 * "diff for <path> (not applied)"). For read_file the result
 * is the file content, not a path, so no target is claimed.
 * Unknown tools fall back to a title-cased tool name.
 */
export function toolDisplayName(name: string, result: string): string {
	const base = (p: string): string => {
		const parts = p.split('/');
		return parts[parts.length - 1] ?? p;
	};
	const wrote = /^wrote (.+?) \(/.exec(result);
	if (name === 'write_file' && wrote) return `Write file: ${base(wrote[1] ?? '')}`;
	const edited = /^edited (.+)$/.exec(result.trim().split('\n')[0] ?? '');
	if (name === 'edit_file' && edited) return `Edit file: ${base(edited[1] ?? '')}`;
	const diff = /^diff for (.+?) \(not applied\)/.exec(result);
	if (name === 'diff_edit' && diff) return `Diff: ${base(diff[1] ?? '')}`;
	const pretty: Record<string, string> = {
		read_file: 'Read file',
		write_file: 'Write file',
		edit_file: 'Edit file',
		diff_edit: 'Diff',
		list_dir: 'List dir',
		search_files: 'Search files',
		run_shell: 'Run shell',
		mcp_call: 'MCP call',
		browser_open: 'Browser open',
		browser_read: 'Browser read',
		browser_watch: 'Browser watch',
		browser_watch_replay: 'Browser watch replay',
		browser_click: 'Browser click',
		browser_click_selector: 'Browser click',
		browser_fill: 'Browser fill',
		browser_fill_selector: 'Browser fill',
		browser_fill_form: 'Browser fill form',
		browser_scroll: 'Browser scroll',
		browser_screenshot: 'Browser screenshot',
		browser_navigate: 'Browser navigate',
		browser_close: 'Browser close',
		count_lines: 'Count lines',
		fuzzy_score: 'Fuzzy score',
	};
	return pretty[name] ?? name.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/** Border colour for a tool card, by status (theme hex values). */
export function toolCardBorderColor(
	status: ToolCardStatus,
	theme: { success: string; warning: string; error: string },
): string {
	if (status === 'running') return theme.warning;
	if (status === 'failed') return theme.error;
	return theme.success;
}

/** Status of a finished tool line, from its real result. */
export function toolLineStatus(result: string): ToolCardStatus {
	return toolStatusMark(result) === '✕' ? 'failed' : 'done';
}
