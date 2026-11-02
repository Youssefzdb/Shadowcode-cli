/** Command palette data for the Shadowcode Ink TUI.
 *
 * One canonical list of slash commands with descriptions.
 * The same list drives /palette (Ctrl+P) and the /help
 * overlay, so the two can never drift apart. Filtering is
 * pure and unit-tested; the App only renders the result.
 */

export interface CommandDef {
	name: string;
	description: string;
}

export const COMMANDS: CommandDef[] = [
	{ name: 'help', description: 'Show the help overlay (Esc closes)' },
	{ name: 'palette', description: 'Open the command palette (Ctrl+P)' },
	{ name: 'theme', description: 'Switch theme: /theme [dark|light|tokyonight|catppuccin]' },
	{ name: 'mode', description: 'Switch mode: /mode [plan|auto|manual] (Plan/Build/Ask)' },
	{ name: 'panel', description: 'Toggle the tools panel (Ctrl+T)' },
	{ name: 'model', description: 'Show or set the model: /model [name]' },
	{ name: 'provider', description: 'Show or set the provider: /provider [name]' },
	{ name: 'tools', description: 'List the agent tools' },
	{ name: 'sessions', description: 'List or search sessions: /sessions [query]' },
	{ name: 'sessions-view', description: 'Session view and actions: /sessions-view <id> info|export|export-file|resume' },
	{ name: 'session-info', description: 'Show info for a session: /session-info <id>' },
	{ name: 'search-sessions', description: 'Search sessions: /search-sessions <q> [--from DATE] [--to DATE]' },
	{ name: 'export', description: 'Export a session: /export <id> [md|json]' },
	{ name: 'export-file', description: 'Export a session to a file: /export-file <id> [md|json] [path]' },
	{ name: 'resume', description: 'Resume a session: /resume <id>' },
	{ name: 'clear', description: 'Clear the transcript' },
	{ name: 'compact', description: 'Compact the current session (extractive)' },
	{ name: 'permissions', description: 'Show the core permission report' },
	{ name: 'browser', description: 'Show preview health, page, driver, watch tail' },
	{ name: 'browser-watch', description: 'Show the browser watch replay (core)' },
	{ name: 'browser-watch-replay', description: 'Show the FULL saved watch replay panel' },
	{ name: 'browser-watch-hide', description: 'Hide the browser watch replay panel' },
	{ name: 'health', description: 'Show the core health report' },
	{ name: 'health-history', description: 'Show health history: /health-history [n]' },
	{ name: 'health-history-hide', description: 'Hide the health history panel' },
	{ name: 'mcp', description: 'MCP servers or tools: /mcp [server]' },
	{ name: 'doctor', description: 'Show the core doctor report' },
	{ name: 'go-search', description: 'Go search first, Python fallback: /go-search <query>' },
	{ name: 'exit', description: 'Quit the TUI (also /quit, Ctrl+C)' },
];

/** Filter commands by query. Name matches rank before
 *  description-only matches; empty query returns all. */
export function filterCommands(query: string): CommandDef[] {
	const q = query.trim().toLowerCase().replace(/^\//, '');
	if (!q) return [...COMMANDS];
	const starts: CommandDef[] = [];
	const nameMatch: CommandDef[] = [];
	const descMatch: CommandDef[] = [];
	for (const cmd of COMMANDS) {
		const name = cmd.name.toLowerCase();
		if (name.startsWith(q)) starts.push(cmd);
		else if (name.includes(q)) nameMatch.push(cmd);
		else if (cmd.description.toLowerCase().includes(q)) descMatch.push(cmd);
	}
	return [...starts, ...nameMatch, ...descMatch];
}
