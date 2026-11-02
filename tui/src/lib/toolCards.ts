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
