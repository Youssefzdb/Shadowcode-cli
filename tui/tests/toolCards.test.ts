import { describe, expect, it } from 'vitest';
import { cardFromToolEvent, completeTool, formatElapsed, startTool, type ToolCard } from '../src/lib/toolCards.js';

describe('tool card state transitions', () => {
	it('goes running -> done with elapsed time', () => {
		let cards: ToolCard[] = [];
		cards = startTool(cards, 'list_dir', 1000);
		expect(cards[0]?.status).toBe('running');
		cards = completeTool(cards, 'list_dir', 'a.txt', 1500);
		expect(cards[0]?.status).toBe('done');
		expect(cards[0]?.elapsedMs).toBe(500);
		expect(formatElapsed(500)).toBe('500ms');
		expect(formatElapsed(1500)).toBe('1.5s');
	});

	it('goes running -> failed on refused / tool-error results', () => {
		let cards = startTool([], 'write_file', 0);
		cards = completeTool(cards, 'write_file', 'refused: password field', 10);
		expect(cards[0]?.status).toBe('failed');
		let cards2 = startTool([], 'run_shell', 0);
		cards2 = completeTool(cards2, 'run_shell', 'tool error: boom', 10);
		expect(cards2[0]?.status).toBe('failed');
	});

	it('completing an unknown tool changes nothing (no fake card)', () => {
		const cards = startTool([], 'list_dir', 0);
		expect(completeTool(cards, 'other_tool', 'x', 5)).toEqual(cards);
	});

	it('completes only the latest running card of the same name', () => {
		let cards = startTool([], 'read_file', 0);
		cards = startTool(cards, 'read_file', 100);
		cards = completeTool(cards, 'read_file', 'ok', 200);
		expect(cards.filter((c) => c.status === 'running')).toHaveLength(1);
		expect(cards.filter((c) => c.status === 'done')).toHaveLength(1);
	});

	it('builds a completed card from a single real tool event', () => {
		const card = cardFromToolEvent('list_dir', 'a.txt', 1000, 1250);
		expect(card.name).toBe('list_dir');
		expect(card.status).toBe('done');
		expect(card.elapsedMs).toBe(250);
	});
});
