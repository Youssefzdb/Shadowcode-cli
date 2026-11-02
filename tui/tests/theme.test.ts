import { describe, expect, it } from 'vitest';
import { isThemeName, resolveTheme, THEME_NAMES, THEMES } from '../src/lib/theme.js';

describe('theme', () => {
	it('defines dark, light, and at least one named theme with all fields', () => {
		for (const name of ['dark', 'light', 'tokyonight', 'catppuccin']) {
			expect(THEME_NAMES).toContain(name);
			const t = THEMES[name];
			for (const field of ['primary', 'secondary', 'success', 'warning', 'error', 'muted', 'user', 'assistant', 'system', 'tool', 'border'] as const) {
				expect(typeof t[field]).toBe('string');
				expect(t[field]).toMatch(/^#[0-9a-f]{6}$/i);
			}
		}
	});

	it('gives each theme a distinct primary colour', () => {
		const primaries = new Set(THEME_NAMES.map((n) => THEMES[n].primary));
		expect(primaries.size).toBe(THEME_NAMES.length);
	});

	it('falls back to dark for unknown names and recognises known ones', () => {
		expect(resolveTheme('nope').name).toBe('dark');
		expect(resolveTheme('light').name).toBe('light');
		expect(isThemeName('tokyonight')).toBe(true);
		expect(isThemeName('nope')).toBe(false);
	});
});
