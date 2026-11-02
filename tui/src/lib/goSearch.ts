/** Optional Go /search backend for the TS TUI (cycle 6).
 *
 * The Go preview server (go/cmd/shadowcode-preview) serves
 * GET /search?q=... -> [{path, line, text, matches}] and
 * GET /health -> {"ok": true}, bound to 127.0.0.1 only.
 *
 * This module is OPTIONAL by design, exactly like the Python
 * native fast path:
 * - If the Go binary was never built (no Go toolchain in this
 *   environment — see MORNING_APPROVALS.md), there is no server
 *   to call, and searchGo() returns null. The caller must fall
 *   back to the Python agent search (search_files tool), never
 *   fake Go hits.
 * - If the server is not running on the given port, fetch
 *   fails and searchGo() returns null — same fallback.
 * - No Go binary is built, installed, or claimed here. This
 *   file only speaks HTTP to a server the user built/started.
 * - The preview port is the same one the Python browser
 *   prints (default 8765, SHADOWCODE_PREVIEW_PORT in the core);
 *   the caller passes it explicitly, it is never guessed from
 *   another service.
 */

import { existsSync } from 'node:fs';
import path from 'node:path';

export interface GoSearchHit {
	path: string;
	line: number;
	text: string;
	matches: number;
}

export function goBinaryPath(tuiDir: string): string {
	// tui/src/lib/goSearch.ts -> repo root is ../../.. from dist,
	// but at source level it is ../.. ; resolve from the TUI dir.
	return path.resolve(tuiDir, '..', 'go', 'shadowcode-preview');
}

export function goBinaryExists(tuiDir: string): boolean {
	return existsSync(goBinaryPath(tuiDir));
}

export async function goServerHealthy(port: number): Promise<boolean> {
	try {
		const res = await fetch(`http://127.0.0.1:${port}/health`, {
			signal: AbortSignal.timeout(2000),
		});
		if (!res.ok) return false;
		const body = (await res.json()) as { ok?: boolean };
		return body.ok === true;
	} catch {
		return false;
	}
}

export interface WatchEntry {
	time?: string;
	title?: string;
	url?: string;
	driver?: string;
}

export interface PreviewState {
	healthy: boolean;
	title: string;
	url: string;
	driver: string;
	hasScreenshot: boolean;
	watch: WatchEntry[];
	lastControlError: string;
}

function parseWatch(value: unknown): WatchEntry[] {
	if (!Array.isArray(value)) return [];
	return value.map((e) => {
		const o = e as Record<string, unknown>;
		return {
			time: String(o.time ?? ''),
			title: String(o.title ?? ''),
			url: String(o.url ?? ''),
			driver: String(o.driver ?? ''),
		};
	});
}

export async function fetchPreviewState(port: number): Promise<PreviewState> {
	const empty: PreviewState = {
		healthy: false, title: '', url: '', driver: '', hasScreenshot: false, watch: [], lastControlError: '',
	};
	const healthy = await goServerHealthy(port);
	if (!healthy) {
		// A Python preview answers /state.json but not /health, so a
		// failed /health check alone must not hide a live Python
		// preview: try /state.json directly before giving up.
		try {
			const res = await fetch(`http://127.0.0.1:${port}/state.json`, {
				signal: AbortSignal.timeout(2000),
			});
			if (!res.ok) return empty;
			const body = (await res.json()) as Record<string, unknown>;
			return {
				healthy: true,
				title: String(body.title ?? ''),
				url: String(body.url ?? ''),
				driver: String(body.driver ?? ''),
				hasScreenshot: body.has_screenshot === true,
				watch: parseWatch(body.watch),
				lastControlError: String(body.last_control_error ?? ''),
			};
		} catch {
			return empty;
		}
	}
	try {
		const res = await fetch(`http://127.0.0.1:${port}/state.json`, {
			signal: AbortSignal.timeout(2000),
		});
		if (!res.ok) return { ...empty, healthy: true };
		const body = (await res.json()) as {
			title?: unknown;
			url?: unknown;
			driver?: unknown;
			has_screenshot?: unknown;
			watch?: unknown;
			last_control_error?: unknown;
		};
		return {
			healthy: true,
			title: String(body.title ?? ''),
			url: String(body.url ?? ''),
			driver: String(body.driver ?? ''),
			hasScreenshot: body.has_screenshot === true,
			watch: parseWatch(body.watch),
			lastControlError: String(body.last_control_error ?? ''),
		};
	} catch {
		return { ...empty, healthy: true };
	}
}

export function formatBrowserPanel(state: PreviewState, port: number): string {
	if (!state.healthy || (!state.url && !state.title)) {
		return [
			'browser preview:',
			'  not started (no live page yet)',
			'  health: unavailable',
			'  start it via the agent, e.g. ask it to: open https://example.com',
			'  then open the preview URL in your own browser to watch live.',
		].join('\n');
	}
	const watch = state.watch.slice(-5);
	const lines = [
		'browser preview:',
		'  health: healthy',
		`  preview url: http://localhost:${port}`,
		`  title: ${state.title}`,
		`  url: ${state.url}`,
		`  driver: ${state.driver}`,
		`  has_screenshot: ${state.hasScreenshot}`,
	];
	if (state.lastControlError) lines.push(`  last_control_error: ${state.lastControlError}`);
	lines.push(
		"  takeover: in the preview, click 'Take control' to drive it yourself;",
		'    the agent pauses and WATCHES (watch log below) while you drive.',
		"  handback: click 'Hand back to agent' in the preview; the agent",
		'    resumes from THIS page exactly — no reload, no reset —',
		'    via browser_watch / browser_read on the current page.',
		`  watch log (last ${watch.length} of ${state.watch.length} shown):`,
	);
	if (watch.length === 0) lines.push('    (no page changes observed yet)');
	for (const e of watch) lines.push(`    ${e.time ?? ''} ${e.title ?? ''} — ${e.url ?? ''} (${e.driver ?? ''})`);
	return lines.join('\n');
}

export async function searchGo(
	port: number,
	query: string,
): Promise<GoSearchHit[] | null> {
	if (!query.trim()) return null;
	try {
		const res = await fetch(
			`http://127.0.0.1:${port}/search?q=${encodeURIComponent(query)}`,
			{ signal: AbortSignal.timeout(5000) },
		);
		if (!res.ok) return null;
		const hits = (await res.json()) as GoSearchHit[];
		if (!Array.isArray(hits)) return null;
		return hits.map((h) => ({
			path: String(h.path ?? ''),
			line: Number(h.line ?? 0),
			text: String(h.text ?? '').slice(0, 200),
			matches: Number(h.matches ?? 0),
		}));
	} catch {
		return null;
	}
}

export function formatGoHits(hits: GoSearchHit[]): string {
	if (hits.length === 0) return 'no matches (Go search)';
	return hits
		.map((h) => `${h.path}:${h.line}: ${h.text}`)
		.join('\n');
}
