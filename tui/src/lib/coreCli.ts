/** Synchronous Python-core CLI calls for TS TUI slash commands
 * (cycle 6 parity with the Python REPL/TUI).
 *
 * The TS TUI is a subprocess UI: its agent turns already spawn
 * `python3 main.py --json-lines ...`. These commands use the
 * core's own exit-and-print flags, which need no session and
 * never write a session file:
 *   --doctor, --search-sessions <q>, --export-session <id>
 *   [--export-format md|json] [--export-output <file>]
 * They run with a short timeout and their output is surfaced
 * verbatim as system lines — never edited, never faked.
 * If the core exits non-zero, the caller shows the failure.
 */
import { spawnSync } from 'node:child_process';

export interface CoreCliResult {
	ok: boolean;
	output: string;
}

export function runCoreCli(
	pythonCore: string,
	args: string[],
	timeoutMs = 15000,
): CoreCliResult {
	try {
		const r = spawnSync('python3', [pythonCore, ...args], {
			encoding: 'utf8',
			timeout: timeoutMs,
		});
		const output = `${r.stdout ?? ''}${r.stderr ?? ''}`.trim();
		return { ok: r.status === 0, output: output || '(no output)' };
	} catch (err) {
		return {
			ok: false,
			output: `core CLI failed: ${err instanceof Error ? err.message : String(err)}`,
		};
	}
}

export function coreDoctor(pythonCore: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--doctor']);
}

export function coreHealth(pythonCore: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--health']);
}

export function coreHealthHistory(
	pythonCore: string,
	workdir: string,
	limit = 10,
): CoreCliResult {
	return runCoreCli(pythonCore, [
		'--workdir',
		workdir,
		'--health-history',
		String(limit),
	]);
}

export function coreBrowserWatch(
	pythonCore: string,
	workdir: string,
): CoreCliResult {
	return runCoreCli(pythonCore, ['--workdir', workdir, '--browser-watch']);
}

export function coreSearchSessions(
	pythonCore: string,
	query: string,
	fromDate?: string,
	toDate?: string,
): CoreCliResult {
	const args = ['--search-sessions', query];
	if (fromDate) args.push('--search-from', fromDate);
	if (toDate) args.push('--search-to', toDate);
	return runCoreCli(pythonCore, args);
}

export function coreListSessions(pythonCore: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--list-sessions']);
}

export function coreSearchFiles(
	pythonCore: string,
	workdir: string,
	query: string,
): CoreCliResult {
	return runCoreCli(pythonCore, ['--workdir', workdir, '--search-files', query]);
}

export function coreCompactSession(
	pythonCore: string,
	id: string,
): CoreCliResult {
	return runCoreCli(pythonCore, ['--compact-session', id]);
}

export function coreSessionInfo(
	pythonCore: string,
	id: string,
): CoreCliResult {
	return runCoreCli(pythonCore, ['--session-info', id]);
}

export function coreMcpServers(pythonCore: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--mcp-servers']);
}

export function coreMcpTools(pythonCore: string, server: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--mcp-tools', server]);
}

export function corePermissions(pythonCore: string): CoreCliResult {
	return runCoreCli(pythonCore, ['--permissions']);
}

export function coreRunShell(
	pythonCore: string,
	workdir: string,
	command: string,
): CoreCliResult {
	return runCoreCli(pythonCore, ['--workdir', workdir, '--run-shell', command]);
}

export function coreExportSession(
	pythonCore: string,
	id: string,
	format: 'md' | 'json' = 'md',
	outputFile?: string,
): CoreCliResult {
	const args = ['--export-session', id, '--export-format', format];
	if (outputFile) args.push('--export-output', outputFile);
	return runCoreCli(pythonCore, args);
}
