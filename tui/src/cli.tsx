#!/usr/bin/env node
/** shadowcode-tui entry point.
 * Non-TTY fallback: if stdin/stdout is not a TTY, print a clear
 * message and exit 0 instead of crashing inside Ink/curses.
 * The Python core remains the agent; this process is only the UI.
 */
import React from 'react';
import { render } from 'ink';
import { App } from './App.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function parseArgs(argv: string[]): Record<string, string> {
	const out: Record<string, string> = {};
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i] ?? '';
		if (a.startsWith('--') && i + 1 < argv.length) {
			out[a.slice(2)] = argv[i + 1] ?? '';
			i++;
		}
	}
	return out;
}

const args = parseArgs(process.argv.slice(2));
if (!process.stdin.isTTY || !process.stdout.isTTY) {
	console.log(
		'Shadowcode TUI needs a terminal (TTY). Falling back gracefully.\n' +
			'Use the Python core instead: ./shadowcode --provider mock --workdir <dir> "your prompt"\n' +
			'Or run this TUI inside a real terminal: ./tui/bin/shadowcode-tui',
	);
	process.exit(0);
}

const here = path.dirname(fileURLToPath(import.meta.url));
// dist/cli.js -> ../../main.py (repo root)
const pythonCore = path.resolve(here, '..', '..', 'main.py');

render(
	React.createElement(App, {
		agent: {
			pythonCore,
			provider: args.provider ?? 'mock',
			model: args.model,
			workdir: args.workdir ?? process.cwd(),
			permissionMode: (args['permission-mode'] as 'manual' | 'auto' | 'plan') ?? 'auto',
			allowDestructive: args['allow-destructive'] === 'true',
		},
		initialSessionId: args.session,
	}),
);
