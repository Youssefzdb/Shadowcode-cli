/** Browser watch replay + health-history helpers for the TS TUI (cycle 10).
 *
 * Replay source of truth is the saved workspace log, not the live
 * preview tail: the Python browser writes every URL/title change
 * (and, since cycle 10, every driver change) to
 * <workdir>/.shadowcode/browser-watch-*.json, so a replay after
 * the browser closed still shows the full log, including both
 * driver transitions (agent -> user on takeover, user -> agent
 * on handback). The live /state.json watch field is only a
 * 10-entry tail and must never be presented as the full replay.
 * A missing/unreadable log is (null, []) — never an invented log.
 */

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

export interface ReplayEntry {
	time?: string;
	title?: string;
	url?: string;
	driver?: string;
	via?: string;
}

/** Cycle 15: classify a watch entry by its ACTION word, not by a
 * substring anywhere in the via string. Via strings are
 * '<driver> <action> <argument>' ('preview scroll to #x',
 * 'preview click (#x)'), and a CSS selector argument can itself
 * contain 'scroll' or 'click' — substring matching would then
 * cross-mark a click as [scroll] or a scroll as [click-driven]. */
export function viaKind(via: string): '' | 'scroll' | 'click' {
	const parts = via.trim().toLowerCase().split(/\s+/).filter(Boolean);
	if (parts.length === 0) return '';
	const action =
		parts.length >= 2 && (parts[0] === 'preview' || parts[0] === 'agent') ? parts[1] : parts[0];
	return action === 'scroll' || action === 'click' ? action : '';
}

export function formatReplayEntries(entries: ReplayEntry[], savedFile = ''): string[] {
	const lines = [
		`browser watch replay: ${entries.length} entries${savedFile ? ` (saved: ${savedFile})` : ''}`,
	];
	if (entries.length === 0) {
		lines.push('  (no page changes observed yet)');
		return lines;
	}
	let prevDriver: string | undefined;
	// Cycle 17: step numbering for multi-step sequences, mirroring
	// Python format_watch_log — action entries (scroll/click) are
	// numbered in order, so scroll -> click -> scroll -> click
	// reads as a sequence. Non-action entries get no step.
	let step = 0;
	let transitions = 0;
	let nScroll = 0;
	let nClick = 0;
	entries.forEach((e, i) => {
		const driver = e.driver ?? '';
		if (prevDriver !== undefined && driver !== prevDriver) {
			lines.push(`  ↳ driver transition: ${prevDriver} -> ${driver}`);
			transitions += 1;
		}
		// Cycle 12 polish: click-driven entries are marked clearly,
		// matching the Python format_watch_log output.
		// Cycle 13: scroll entries get the same treatment.
		// Cycle 15: viaKind (action prefix), not substring, so a
		// selector argument cannot cross-mark the entry.
		const via = e.via ?? '';
		const kind = viaKind(via);
		const clickMark = kind === 'click' ? ' [click-driven]' : '';
		const scrollMark = kind === 'scroll' ? ' [scroll]' : '';
		let stepMark = '';
		if (kind === 'click') {
			nClick += 1;
			step += 1;
			stepMark = ` [step ${step}]`;
		}
		if (kind === 'scroll') {
			nScroll += 1;
			step += 1;
			stepMark = ` [step ${step}]`;
		}
		const suffix = via ? ` via ${via}${clickMark}${scrollMark}${stepMark}` : '';
		lines.push(`  ${i + 1}. ${e.time ?? ''} ${e.title ?? ''} — ${e.url ?? ''} (${driver})${suffix}`);
		prevDriver = driver;
	});
	if (step > 0) {
		lines.push(
			`  steps: ${nScroll} scroll, ${nClick} click-driven, ${transitions} driver transition${transitions === 1 ? '' : 's'} (${step} action step${step === 1 ? '' : 's'})`,
		);
	}
	return lines;
}

export function countClickDriven(entries: ReplayEntry[]): number {
	return entries.filter((e) => viaKind(e.via ?? '') === 'click').length;
}

export function countScroll(entries: ReplayEntry[]): number {
	return entries.filter((e) => viaKind(e.via ?? '') === 'scroll').length;
}

export function countTransitions(entries: ReplayEntry[]): number {
	let count = 0;
	for (let i = 1; i < entries.length; i++) {
		if (entries[i]?.driver !== entries[i - 1]?.driver) count++;
	}
	return count;
}

export function readSavedWatchLog(workdir: string): { file: string | null; entries: ReplayEntry[] } {
	try {
		const dir = path.join(workdir, '.shadowcode');
		if (!existsSync(dir)) return { file: null, entries: [] };
		const files = readdirSync(dir)
			.filter((f) => f.startsWith('browser-watch-') && f.endsWith('.json'))
			.map((f) => path.join(dir, f))
			.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
		if (files.length === 0) return { file: null, entries: [] };
		const parsed: unknown = JSON.parse(readFileSync(files[0] ?? '', 'utf8'));
		if (!Array.isArray(parsed)) return { file: files[0] ?? null, entries: [] };
		const entries: ReplayEntry[] = parsed
			.filter((e): e is Record<string, unknown> => typeof e === 'object' && e !== null && typeof e.url === 'string')
			.map((e) => ({
				time: String(e.time ?? ''),
				title: String(e.title ?? ''),
				url: String(e.url ?? ''),
				driver: String(e.driver ?? ''),
				via: typeof e.via === 'string' ? e.via : undefined,
			}));
		return { file: files[0] ?? null, entries };
	} catch {
		return { file: null, entries: [] };
	}
}

/** Health-history panel lines: the core's --health-history output,
 * split into display lines, with no line invented. An empty output
 * is reported as such, never as a fake snapshot. */
export function healthHistoryLines(output: string): string[] {
	const lines = output.split('\n').map((l) => l.trimEnd()).filter((l) => l.length > 0);
	return lines.length > 0 ? lines : ['health history: no output from the core'];
}
