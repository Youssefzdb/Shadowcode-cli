import { describe, expect, it } from 'vitest';
import { applyEvent, parseEventLine, toolStatusMark, truncate, type TranscriptLine } from '../src/lib/protocol.js';
import { buildArgs } from '../src/lib/agent.js';

describe('protocol', () => {
	it('parses token/tool/final/session lines', () => {
		expect(parseEventLine('{"type":"token","text":"hi"}')).toEqual({ type: 'token', text: 'hi' });
		expect(parseEventLine('{"type":"tool","name":"list_dir","result":"a"}')).toEqual({
			type: 'tool',
			name: 'list_dir',
			result: 'a',
		});
		expect(parseEventLine('not json')).toMatchObject({ type: 'error' });
		expect(parseEventLine('')).toBeNull();
	});

	it('folds tokens into one assistant line and does not duplicate finals', () => {
		let lines: TranscriptLine[] = [];
		lines = applyEvent(lines, { type: 'token', text: 'Hello ' });
		lines = applyEvent(lines, { type: 'token', text: 'world' });
		// Final immediately after streaming = same reply, no duplicate.
		lines = applyEvent(lines, { type: 'final', text: 'Hello world' });
		expect(lines).toHaveLength(1);
		expect(lines[0]).toEqual({ kind: 'assistant', text: 'Hello world' });
		// Final after a tool call is a NEW assistant turn, not a duplicate.
		lines = applyEvent(lines, { type: 'tool', name: 'list_dir', result: 'a.txt' });
		lines = applyEvent(lines, { type: 'final', text: 'Done.' });
		expect(lines).toHaveLength(3);
		expect(lines[2]).toEqual({ kind: 'assistant', text: 'Done.' });
	});

	it('marks refused/error tools', () => {
		expect(toolStatusMark('refused: password field')).toBe('✕');
		expect(toolStatusMark('tool error: boom')).toBe('✕');
		expect(toolStatusMark('wrote x')).toBe('✓');
		expect(truncate('abcdef', 3)).toBe('abc…');
	});
});

describe('agent args', () => {
	it('builds a json-lines subprocess call with resume or fresh id', () => {
		const base = { pythonCore: '/x/main.py', provider: 'mock', workdir: '/tmp/w' };
		const resumed = buildArgs(base, 'abc123', 'list files');
		expect(resumed).toContain('--json-lines');
		expect(resumed).toContain('--resume');
		expect(resumed).toContain('abc123');
		const fresh = buildArgs(base, null, 'hi');
		expect(fresh).toContain('--session-id');
		expect(fresh).not.toContain('--resume');
	});
});
