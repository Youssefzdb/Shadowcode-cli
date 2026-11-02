/** Spawning the Python Shadowcode core as a subprocess.
 * One subprocess per user turn (see PROTOCOL.md): the first turn
 * passes --session-id <new-id>, later turns pass --resume <id>, so
 * history lives in the Python session file, not in this process.
 * Permission model in subprocess mode: --permission-mode auto for
 * non-destructive tools; destructive tools stay guarded unless the
 * user passes --allow-destructive explicitly. No interactive stdin
 * permission prompt is faked. */
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { parseEventLine, type AgentEvent } from './protocol.js';

export interface AgentOptions {
	pythonCore: string; // path to ~/workspace/shadowcode/main.py
	provider: string;
	model?: string;
	workdir: string;
	permissionMode?: 'manual' | 'auto' | 'plan';
	allowDestructive?: boolean;
}

export interface AgentHandle {
	events: AsyncIterable<AgentEvent>;
	wait: () => Promise<{ code: number | null }>;
	kill: () => void;
}

export function newSessionId(): string {
	return randomUUID().replace(/-/g, '').slice(0, 12);
}

export function buildArgs(opts: AgentOptions, sessionId: string | null, prompt: string): string[] {
	const args = [
		opts.pythonCore,
		'--json-lines',
		'--no-tui',
		'--provider',
		opts.provider,
		'--workdir',
		opts.workdir,
		'--permission-mode',
		opts.permissionMode ?? 'auto',
	];
	if (opts.model) args.push('--model', opts.model);
	if (opts.allowDestructive) args.push('--allow-destructive', '--yes');
	if (sessionId) {
		args.push('--resume', sessionId);
	} else {
		args.push('--session-id', newSessionId());
	}
	args.push(prompt);
	return args;
}

export function runTurn(
	opts: AgentOptions,
	sessionId: string | null,
	prompt: string,
): AgentHandle {
	const child = spawn('python3', buildArgs(opts, sessionId, prompt), {
		stdio: ['ignore', 'pipe', 'pipe'],
	});
	let buffer = '';
	const queue: AgentEvent[] = [];
	const waiters: Array<() => void> = [];
	let done = false;
	const push = (ev: AgentEvent) => {
		queue.push(ev);
		for (const w of waiters.splice(0)) w();
	};
	child.stdout.on('data', (chunk: Buffer) => {
		buffer += chunk.toString('utf8');
		let idx: number;
		while ((idx = buffer.indexOf('\n')) >= 0) {
			const line = buffer.slice(0, idx);
			buffer = buffer.slice(idx + 1);
			const ev = parseEventLine(line);
			if (ev) push(ev);
		}
	});
	child.stderr.on('data', (chunk: Buffer) => {
		const text = chunk.toString('utf8').trim();
		if (text) push({ type: 'error', message: text.slice(0, 500) });
	});
	child.on('close', () => {
		if (buffer.trim()) {
			const ev = parseEventLine(buffer);
			if (ev) push(ev);
		}
		done = true;
		for (const w of waiters.splice(0)) w();
	});
	const events: AsyncIterable<AgentEvent> = {
		async *[Symbol.asyncIterator]() {
			while (true) {
				while (queue.length > 0) {
					yield queue.shift() as AgentEvent;
				}
				if (done) return;
				await new Promise<void>((resolve) => waiters.push(resolve));
			}
		},
	};
	return {
		events,
		wait: () =>
			new Promise<{ code: number | null }>((resolve) => {
				child.on('close', (code) => resolve({ code }));
			}),
		kill: () => child.kill(),
	};
}
