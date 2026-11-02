import { describe, expect, it } from 'vitest';
import { buildArgs } from '../src/lib/agent.js';
import { modeInfo, modeLabel, parseMode } from '../src/lib/mode.js';

describe('mode mapping', () => {
	it('maps Plan/Build/Ask labels to the exact core permission modes', () => {
		expect(parseMode('plan')).toBe('plan');
		expect(parseMode('auto')).toBe('auto');
		expect(parseMode('build')).toBe('auto');
		expect(parseMode('manual')).toBe('manual');
		expect(parseMode('ask')).toBe('manual');
		expect(modeLabel('plan')).toBe('Plan');
		expect(modeLabel('auto')).toBe('Build');
		expect(modeLabel('manual')).toBe('Ask');
		expect(modeInfo('plan').description).toMatch(/read-only/i);
	});

	it('rejects unknown modes instead of inventing one', () => {
		expect(parseMode('turbo')).toBeNull();
		expect(parseMode('')).toBeNull();
	});

	it('passes the mapped mode verbatim to the core subprocess', () => {
		const base = { pythonCore: '/x/main.py', provider: 'mock', workdir: '/tmp/w' };
		for (const [input, core] of [['build', 'auto'], ['ask', 'manual'], ['plan', 'plan']] as const) {
			const mode = parseMode(input);
			const args = buildArgs({ ...base, permissionMode: mode ?? 'auto' }, null, 'hi');
			const idx = args.indexOf('--permission-mode');
			expect(args[idx + 1]).toBe(core);
		}
	});
});
