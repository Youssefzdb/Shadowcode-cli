/** Theme system for the Shadowcode Ink TUI.
 *
 * Colours are defined ONCE here and passed down as a Theme object;
 * components must not hard-code 'gray'/'cyan'/'yellow' everywhere.
 * Palettes are original hex values in a familiar dark/light/
 * tokyonight/catppuccin *style* — no colour scheme was copied
 * from Claude Code, OpenCode, or Kilo Code source.
 *
 * Ink Text `color` accepts hex strings (via chalk), so a theme
 * can be swapped at runtime with /theme without touching any
 * component. Unknown names fall back to 'dark', never crash.
 */

export interface Theme {
	name: string;
	label: string;
	primary: string;
	secondary: string;
	success: string;
	warning: string;
	error: string;
	muted: string;
	user: string;
	assistant: string;
	system: string;
	tool: string;
	border: string;
}

export const THEMES: Record<string, Theme> = {
	dark: {
		name: 'dark',
		label: 'Dark',
		primary: '#00d7ff',
		secondary: '#c586c0',
		success: '#4ec9b0',
		warning: '#dcdcaa',
		error: '#f44747',
		muted: '#808080',
		user: '#4ec9b0',
		assistant: '#d4d4d4',
		system: '#808080',
		tool: '#dcdcaa',
		border: '#3e3e42',
	},
	light: {
		name: 'light',
		label: 'Light',
		primary: '#0b5fff',
		secondary: '#8250df',
		success: '#1a7f37',
		warning: '#9a6700',
		error: '#cf222e',
		muted: '#57606a',
		user: '#1a7f37',
		assistant: '#24292f',
		system: '#57606a',
		tool: '#9a6700',
		border: '#d0d7de',
	},
	tokyonight: {
		name: 'tokyonight',
		label: 'Tokyo Night',
		primary: '#7aa2f7',
		secondary: '#bb9af7',
		success: '#9ece6a',
		warning: '#e0af68',
		error: '#f7768e',
		muted: '#565f89',
		user: '#9ece6a',
		assistant: '#c0caf5',
		system: '#565f89',
		tool: '#e0af68',
		border: '#292e42',
	},
	catppuccin: {
		name: 'catppuccin',
		label: 'Catppuccin Mocha',
		primary: '#89b4fa',
		secondary: '#cba6f7',
		success: '#a6e3a1',
		warning: '#f9e2af',
		error: '#f38ba8',
		muted: '#6c7086',
		user: '#a6e3a1',
		assistant: '#cdd6f4',
		system: '#6c7086',
		tool: '#f9e2af',
		border: '#313244',
	},
	// Claude-style layout theme (Design 1, user-chosen mockup):
	// near-black background is the terminal's own background (Ink
	// does not paint a background), purple wordmark + cyan
	// assistant lines, green tool cards. Original hex values in
	// that style, not copied from any other product's source.
	'claude-dark': {
		name: 'claude-dark',
		label: 'Claude Dark',
		primary: '#a78bfa',
		secondary: '#67e8f9',
		success: '#4ade80',
		warning: '#facc15',
		error: '#f87171',
		muted: '#9ca3af',
		user: '#c084fc',
		assistant: '#67e8f9',
		system: '#9ca3af',
		tool: '#4ade80',
		border: '#374151',
	},
};

export const THEME_NAMES: string[] = Object.keys(THEMES);

export function isThemeName(name: string): name is keyof typeof THEMES {
	return name in THEMES;
}

/** Resolve a theme by name; unknown names fall back to dark. */
export function resolveTheme(name: string): Theme {
	return THEMES[name] ?? (THEMES.dark as Theme);
}
