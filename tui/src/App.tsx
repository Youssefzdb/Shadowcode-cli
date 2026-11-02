import React, { useCallback, useEffect, useRef, useState } from 'react';
import path from 'node:path';
import { Box, Text, useApp, useInput } from 'ink';
import { Header } from './components/Header.js';
import { Transcript } from './components/Transcript.js';
import { ToolPanel } from './components/ToolPanel.js';
import { StatusBar } from './components/StatusBar.js';
import { Input } from './components/Input.js';
import { PermissionPrompt } from './components/PermissionPrompt.js';
import { applyEvent, type TranscriptLine } from './lib/protocol.js';
import { runTurn, type AgentOptions } from './lib/agent.js';
import {
	coreBrowserWatch,
	coreCompactSession,
	coreDoctor,
	coreExportSession,
	coreHealth,
	coreHealthHistory,
	coreListSessions,
	coreMcpServers,
	coreMcpTools,
	corePermissions,
	coreRunShell,
	coreSearchFiles,
	coreSearchSessions,
	coreSessionInfo,
} from './lib/coreCli.js';
import { fetchPreviewState, formatBrowserPanel, formatGoHits, goBinaryExists, searchGo, type WatchEntry } from './lib/goSearch.js';
import { BrowserWatchPanel } from './components/BrowserWatchPanel.js';
import { HealthHistoryPanel } from './components/HealthHistoryPanel.js';
import { formatReplayEntries, healthHistoryLines, readSavedWatchLog, type ReplayEntry } from './lib/replay.js';

export interface AppProps {
	agent: AgentOptions;
	initialSessionId?: string;
}

const HELP = [
	'/help /model [name] /provider [name] /tools /sessions [query]',
	'/sessions-view [query] /sessions-view <id> info|export|export-file|resume /session-info <id>',
	'/search-sessions <q> [--from YYYY-MM-DD] [--to YYYY-MM-DD] /export <id> [md|json] /export-file <id> [md|json] [path]',
	'/resume <id> /clear /compact /permissions /browser /browser-watch /browser-watch-replay /browser-watch-hide /health /health-history [n] /health-history-hide /mcp [server] /doctor',
	'/browser-watch-replay shows the FULL saved replay (all entries, both driver transitions) as a panel, not the 10-entry live tail',
	'/go-search <query> — Go /search first, Python search_files fallback (real, not a hint)',
	'/browser shows preview health, title, URL, driver, takeover/handback hints, watch log tail',
	'/health shows python core, TS TUI, Go preview, native scanner, Playwright (honest, never faked)',
	'/exit — !cmd runs a shell command in the workdir (via the Python core).',
	'Up/Down = history. Ctrl-C, or /exit, to quit.',
	'Slash commands are handled locally; anything else goes to the agent.',
	'Permission note: in subprocess mode destructive tools are denied',
	'unless --allow-destructive was passed; no prompt is faked here.',
];

export function App(props: AppProps): React.ReactElement {
	const { exit } = useApp();
	const [lines, setLines] = useState<TranscriptLine[]>([
		{ kind: 'system', text: 'Shadowcode TUI — type /help for commands, /exit to quit.' },
	]);
	const [input, setInput] = useState('');
	const [history, setHistory] = useState<string[]>([]);
	const [histIdx, setHistIdx] = useState<number | null>(null);
	const [thinking, setThinking] = useState(false);
	const [toolCount, setToolCount] = useState(0);
	const [lastTool, setLastTool] = useState('');
	const [sessionId, setSessionId] = useState<string>(props.initialSessionId ?? '');
	const [browserUrl, setBrowserUrl] = useState<string>('');
	const [browserDriver, setBrowserDriver] = useState<string>('agent');
	const [previewHealthy, setPreviewHealthy] = useState<boolean | null>(null);
	const [previewTitle, setPreviewTitle] = useState<string>('');
	const [browserWatch, setBrowserWatch] = useState<WatchEntry[]>([]);
	const [browserPageUrl, setBrowserPageUrl] = useState<string>('');
	const [replayEntries, setReplayEntries] = useState<ReplayEntry[] | null>(null);
	const [replayFile, setReplayFile] = useState<string | null>(null);
	const [healthPanel, setHealthPanel] = useState<string[] | null>(null);
	const [goPort] = useState<number>(() => {
		const p = Number(process.env.SHADOWCODE_PREVIEW_PORT ?? '8765');
		return Number.isFinite(p) && p > 0 ? p : 8765;
	});
	const [permission, setPermission] = useState<string | null>(null);
	const sessionRef = useRef(sessionId);
	sessionRef.current = sessionId;

	const append = useCallback((line: TranscriptLine) => {
		setLines((prev) => [...prev, line]);
	}, []);

	// Go/Python preview health display: poll localhost only, every 3s.
	// This is the same /state.json shape the Python browser and the Go
	// preview server both serve. A failed poll means "unavailable",
	// never a faked healthy state. When the preview reports a URL or
	// driver, the header/status follow it (agent watches user driving).
	useEffect(() => {
		let stopped = false;
		const poll = async () => {
			const port = Number(process.env.SHADOWCODE_PREVIEW_PORT ?? '8765');
			const safePort = Number.isFinite(port) && port > 0 ? port : 8765;
			const st = await fetchPreviewState(safePort);
			if (stopped) return;
			setPreviewHealthy(st.healthy);
			if (st.url) {
				setBrowserUrl(`http://127.0.0.1:${safePort}`);
				setBrowserPageUrl(st.url);
			}
			if (st.driver) setBrowserDriver(st.driver);
			if (st.title) setPreviewTitle(st.title);
			setBrowserWatch(st.watch);
		};
		void poll();
		const timer = setInterval(() => void poll(), 3000);
		return () => {
			stopped = true;
			clearInterval(timer);
		};
	}, []);

	const submit = useCallback(
		async (text: string) => {
			const trimmed = text.trim();
			if (!trimmed) return;
			setHistory((h) => [...h, trimmed]);
			setHistIdx(null);
			append({ kind: 'user', text: trimmed });
			if (trimmed === '/exit' || trimmed === '/quit') {
				exit();
				return;
			}
			if (trimmed === '/help') {
				for (const h of HELP) append({ kind: 'system', text: h });
				return;
			}
			if (trimmed === '/clear') {
				setLines([]);
				return;
			}
			if (trimmed === '/tools') {
				append({
					kind: 'system',
					text: 'read_file write_file edit_file diff_edit list_dir search_files run_shell mcp_call browser_open browser_read browser_watch browser_watch_replay browser_click browser_click_selector browser_fill browser_fill_selector browser_fill_form browser_scroll browser_screenshot browser_navigate browser_close',
				});
				return;
			}
			if (trimmed === '/sessions') {
				const r = coreListSessions(props.agent.pythonCore);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed.startsWith('/provider ')) {
				const name = trimmed.split(/\s+/)[1] ?? '';
				props.agent.provider = name;
				append({ kind: 'system', text: `provider=${name}` });
				return;
			}
			if (trimmed.startsWith('/model ')) {
				const name = trimmed.split(/\s+/)[1] ?? '';
				props.agent.model = name;
				append({ kind: 'system', text: `model=${name}` });
				return;
			}
			if (trimmed === '/model') {
				append({ kind: 'system', text: `model=${props.agent.model ?? '(default)'}` });
				return;
			}
			if (trimmed === '/provider') {
				append({ kind: 'system', text: `provider=${props.agent.provider}` });
				return;
			}
			if (trimmed.startsWith('/sessions')) {
				const q = trimmed.split(/\s+/).slice(1).join(' ');
				if (!q) {
					const r = coreListSessions(props.agent.pythonCore);
					append({ kind: 'system', text: r.output });
				} else {
					const r = coreSearchSessions(props.agent.pythonCore, q);
					append({ kind: 'system', text: r.output });
				}
				return;
			}
			if (trimmed.startsWith('/search-sessions ')) {
				// /search-sessions <q> [--from YYYY-MM-DD] [--to YYYY-MM-DD]
				const parts = trimmed.split(/\s+/).slice(1);
				const queryParts: string[] = [];
				let fromDate: string | undefined;
				let toDate: string | undefined;
				for (let i = 0; i < parts.length; i++) {
					if (parts[i] === '--from' && parts[i + 1]) fromDate = parts[++i];
					else if (parts[i] === '--to' && parts[i + 1]) toDate = parts[++i];
					else queryParts.push(parts[i] ?? '');
				}
				const r = coreSearchSessions(props.agent.pythonCore, queryParts.join(' '), fromDate, toDate);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed.startsWith('/export')) {
				const parts = trimmed.split(/\s+/);
				if (parts.length < 2) {
					append({ kind: 'system', text: 'usage: /export <id> [md|json]  /export-file <id> [md|json] [path]' });
					return;
				}
				const isFile = parts[0] === '/export-file';
				const fmt = (parts[2] === 'json' ? 'json' : 'md') as 'md' | 'json';
				const outFile = isFile ? parts[3] : undefined;
				const r = coreExportSession(props.agent.pythonCore, parts[1] ?? '', fmt, outFile);
				append({ kind: 'system', text: r.output.slice(0, 2000) });
				return;
			}
			if (trimmed.startsWith('/resume ')) {
				const id = trimmed.split(/\s+/)[1] ?? '';
				const info = coreSessionInfo(props.agent.pythonCore, id);
				setSessionId(id);
				sessionRef.current = id;
				append({ kind: 'system', text: info.ok ? `resumed: ${info.output} (next turn uses --resume ${id})` : `resume failed: ${info.output}` });
				return;
			}
			if (trimmed === '/compact') {
				const id = sessionRef.current;
				if (!id) {
					append({ kind: 'system', text: 'compact: no session yet — send a prompt first, then /compact.' });
					return;
				}
				const r = coreCompactSession(props.agent.pythonCore, id);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed === '/permissions') {
				const r = corePermissions(props.agent.pythonCore);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed === '/browser') {
				const st = await fetchPreviewState(goPort);
				if (st.url) setBrowserPageUrl(st.url);
				if (st.driver) setBrowserDriver(st.driver);
				if (st.title) setPreviewTitle(st.title);
				setBrowserWatch(st.watch);
				setPreviewHealthy(st.healthy);
				append({ kind: 'system', text: formatBrowserPanel(st, goPort) });
				return;
			}
			if (trimmed === '/health') {
				const r = coreHealth(props.agent.pythonCore);
				const tsNote = `typescript tui: this Ink/React UI (package @shadowcode/tui) | go binary built=${goBinaryExists(path.join(path.dirname(props.agent.pythonCore), 'tui'))} | preview watch entries=${browserWatch.length}`;
				append({ kind: 'system', text: `${r.output}\n${tsNote}` });
				return;
			}
			if (trimmed === '/health-history-hide') {
				setHealthPanel(null);
				append({ kind: 'system', text: 'health-history panel hidden.' });
				return;
			}
			if (trimmed.startsWith('/health-history')) {
				const n = Number(trimmed.split(/\s+/)[1] ?? '10');
				const r = coreHealthHistory(
					props.agent.pythonCore,
					props.agent.workdir,
					Number.isFinite(n) ? n : 10,
				);
				setHealthPanel(healthHistoryLines(r.output));
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed === '/browser-watch') {
				const r = coreBrowserWatch(props.agent.pythonCore, props.agent.workdir);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed === '/browser-watch-replay') {
				// Full replay panel, from the saved workspace log
				// (not the live 10-entry tail). If no browser has
				// run yet, the panel honestly shows "no page
				// changes observed yet" instead of a fake log.
				const saved = readSavedWatchLog(props.agent.workdir);
				setReplayEntries(saved.entries);
				setReplayFile(saved.file);
				for (const l of formatReplayEntries(saved.entries, saved.file ?? '')) {
					append({ kind: 'system', text: l });
				}
				return;
			}
			if (trimmed === '/browser-watch-hide') {
				setReplayEntries(null);
				setReplayFile(null);
				append({ kind: 'system', text: 'browser watch replay panel hidden.' });
				return;
			}
			if (trimmed.startsWith('/sessions-view')) {
				const parts = trimmed.split(/\s+/).slice(1);
				// Cycle 9 actions, via the same core flags the other
				// TS commands use (no TS code edits a session file):
				//   /sessions-view <id> info | export [md|json]
				//   /sessions-view <id> export-file [md|json] [path]
				//   /sessions-view <id> resume
				// Anything else is the old list/search view.
				if (parts.length >= 2 && ['info', 'export', 'export-file', 'resume'].includes(parts[1] ?? '')) {
					const id = parts[0] ?? '';
					const action = parts[1] ?? '';
					if (action === 'info') {
						append({ kind: 'system', text: coreSessionInfo(props.agent.pythonCore, id).output });
					} else if (action === 'export') {
						const fmt = (parts[2] === 'json' ? 'json' : 'md') as 'md' | 'json';
						append({ kind: 'system', text: coreExportSession(props.agent.pythonCore, id, fmt).output.slice(0, 2000) });
					} else if (action === 'export-file') {
						const fmt = (parts[2] === 'json' ? 'json' : 'md') as 'md' | 'json';
						append({ kind: 'system', text: coreExportSession(props.agent.pythonCore, id, fmt, parts[3]).output });
					} else if (action === 'resume') {
						const info = coreSessionInfo(props.agent.pythonCore, id);
						setSessionId(id);
						sessionRef.current = id;
						append({ kind: 'system', text: info.ok ? `resumed: ${info.output} (next turn uses --resume ${id})` : `resume failed: ${info.output}` });
					}
					return;
				}
				const q = parts.join(' ');
				const list = q ? coreSearchSessions(props.agent.pythonCore, q) : coreListSessions(props.agent.pythonCore);
				append({
					kind: 'system',
					text: `sessions view:\n${list.output}\n  actions: /resume <id> (load in memory)  /export <id> [md|json]  /export-file <id> [md|json] [path]  /session-info <id>  /compact (current session only, approved path)\n  from this view: /sessions-view <id> info | export [md|json] | export-file [md|json] [path] | resume\n  note: listing/searching/info/export never edit a session file.`,
				});
				return;
			}
			if (trimmed.startsWith('/session-info ')) {
				const id = trimmed.split(/\s+/)[1] ?? '';
				const info = coreSessionInfo(props.agent.pythonCore, id);
				append({ kind: 'system', text: info.output });
				return;
			}
			if (trimmed.startsWith('/mcp')) {
				const parts = trimmed.split(/\s+/);
				const r = parts.length > 1 ? coreMcpTools(props.agent.pythonCore, parts[1] ?? '') : coreMcpServers(props.agent.pythonCore);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed === '/doctor') {
				const r = coreDoctor(props.agent.pythonCore);
				append({ kind: 'system', text: r.output });
				return;
			}
			if (trimmed.startsWith('/go-search ')) {
				const q = trimmed.split(/\s+/).slice(1).join(' ');
				const hits = await searchGo(goPort, q);
				if (hits !== null) {
					append({ kind: 'system', text: `Go search (localhost:${goPort}):\n${formatGoHits(hits)}` });
				} else {
					// Real Python fallback, not a hint: the core's
					// search_files (native C++ fast path when present,
					// pure Python otherwise) via --search-files.
					const fb = coreSearchFiles(props.agent.pythonCore, props.agent.workdir, q);
					append({ kind: 'system', text: `Go search unavailable (binary built=${goBinaryExists(path.join(path.dirname(props.agent.pythonCore), 'tui'))}). Python fallback:\n${fb.output}` });
				}
				return;
			}
			if (trimmed.startsWith('!')) {
				const cmd = trimmed.slice(1).trim();
				if (!cmd) {
					append({ kind: 'system', text: 'usage: !<shell command> (runs in the workdir, same as the Python REPL)' });
					return;
				}
				const r = coreRunShell(props.agent.pythonCore, props.agent.workdir, cmd);
				append({ kind: 'tool', name: 'run_shell', result: r.output });
				return;
			}
			setThinking(true);
			try {
				const handle = runTurn(props.agent, sessionRef.current || null, trimmed);
				for await (const ev of handle.events) {
					if (ev.type === 'session') {
						setSessionId(ev.id);
						sessionRef.current = ev.id;
					} else if (ev.type === 'tool') {
						setToolCount((c) => c + 1);
						setLastTool(ev.name);
						if (ev.name === 'browser_open' || ev.name === 'browser_screenshot') {
							const m = /localhost:\d+/.exec(ev.result);
							if (m) setBrowserUrl(`http://${m[0]}`);
						}
					}
					setLines((prev) => applyEvent(prev, ev));
				}
				await handle.wait();
			} catch (err) {
				append({ kind: 'system', text: `agent error: ${err instanceof Error ? err.message : String(err)}` });
			} finally {
				setThinking(false);
			}
		},
		[append, exit, props.agent],
	);

	useInput((inputChar, key) => {
		if (key.ctrl && inputChar === 'c') {
			exit();
			return;
		}
		if (key.return) {
			const text = input;
			setInput('');
			void submit(text);
			return;
		}
		if (key.upArrow && history.length > 0) {
			const idx = histIdx === null ? history.length - 1 : Math.max(0, histIdx - 1);
			setHistIdx(idx);
			setInput(history[idx] ?? '');
			return;
		}
		if (key.downArrow && histIdx !== null) {
			const idx = Math.min(history.length - 1, histIdx + 1);
			setHistIdx(idx);
			setInput(history[idx] ?? '');
			return;
		}
		if (key.backspace || key.delete) {
			setInput((v) => v.slice(0, -1));
			return;
		}
		if (inputChar) {
			setInput((v) => v + inputChar);
		}
	});

	useEffect(() => {
		// PermissionPrompt is a documented placeholder for interactive
		// prompts in subprocess mode: the Python core in auto mode
		// denies destructive tools unless --allow-destructive is set,
		// so no prompt is faked here. Kept as a component for the
		// future interactive (non-subprocess) agent mode.
		setPermission(null);
	}, []);

	return (
		<Box flexDirection="column" height="100%">
			<Header
				provider={props.agent.provider}
				model={props.agent.model ?? ''}
				sessionId={sessionId}
				permissionMode={props.agent.permissionMode ?? 'auto'}
				browserUrl={browserUrl}
				browserDriver={browserUrl ? browserDriver : undefined}
				browserTitle={previewTitle || undefined}
				browserHealth={previewHealthy}
			/>
			<Transcript lines={lines} />
			<ToolPanel lines={lines} />
			{replayEntries !== null ? <BrowserWatchPanel entries={replayEntries} savedFile={replayFile} /> : null}
			{healthPanel !== null ? <HealthHistoryPanel lines={healthPanel} /> : null}
			{permission ? <PermissionPrompt prompt={permission} onAnswer={() => setPermission(null)} /> : null}
			<StatusBar status="Ready" thinking={thinking} toolCount={toolCount} lastTool={lastTool} messageCount={lines.length} previewHealthy={previewHealthy} previewPort={goPort} previewDriver={browserDriver} previewTitle={previewTitle || undefined} previewUrl={browserPageUrl || undefined} />
			<Input value={input} />
			<Text color="gray">Tip: browser preview URL appears in the header when the agent opens the browser.</Text>
		</Box>
	);
}
