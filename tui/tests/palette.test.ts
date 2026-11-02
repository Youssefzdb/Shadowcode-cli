import { describe, expect, it } from 'vitest';
import { COMMANDS, filterCommands } from '../src/lib/palette.js';

describe('command palette filtering', () => {
	it('returns all commands for an empty query', () => {
		expect(filterCommands('')).toHaveLength(COMMANDS.length);
		expect(filterCommands('/')).toHaveLength(COMMANDS.length);
	});

	it('matches by name, case-insensitively', () => {
		const names = filterCommands('THEME').map((c) => c.name);
		expect(names).toContain('theme');
	});

	it('ranks name matches before description-only matches', () => {
		// 'theme' is a name match and must come first; 'switch'
		// appears only in the theme/mode descriptions.
		const byName = filterCommands('theme');
		expect(byName[0]?.name).toBe('theme');
		const byDesc = filterCommands('switch');
		expect(byDesc.map((c) => c.name)).toContain('theme');
		expect(byDesc.map((c) => c.name)).toContain('mode');
		expect(byDesc.some((c) => c.name === 'sessions')).toBe(false);
	});

	it('includes the new theme/mode/palette/panel commands', () => {
		const names = COMMANDS.map((c) => c.name);
		for (const n of ['theme', 'mode', 'palette', 'panel', 'help', 'exit']) expect(names).toContain(n);
	});

	it('returns nothing for a query matching nothing', () => {
		expect(filterCommands('zzzz-no-such-command')).toHaveLength(0);
	});
});
