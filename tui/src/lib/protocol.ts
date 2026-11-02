/** JSON-lines protocol between the Shadowcode TS TUI and the Python core.
 * See PROTOCOL.md. Pure functions only — unit-tested, no Ink here. */

export type AgentEvent =
	| { type: 'token'; text: string }
	| { type: 'tool'; name: string; result: string }
	| { type: 'final'; text: string }
	| { type: 'session'; id: string }
	| { type: 'error'; message: string };

export function parseEventLine(line: string): AgentEvent | null {
	const trimmed = line.trim();
	if (!trimmed) return null;
	try {
		const obj = JSON.parse(trimmed) as Record<string, unknown>;
		if (typeof obj.type !== 'string') return null;
		switch (obj.type) {
			case 'token':
				return { type: 'token', text: String(obj.text ?? '') };
			case 'tool':
				return { type: 'tool', name: String(obj.name ?? ''), result: String(obj.result ?? '') };
			case 'final':
				return { type: 'final', text: String(obj.text ?? '') };
			case 'session':
				return { type: 'session', id: String(obj.id ?? '') };
			default:
				return null;
		}
	} catch {
		// Non-JSON output from the subprocess is not a protocol event;
		// the caller surfaces it as an error line, never silently.
		return { type: 'error', message: `non-JSON output: ${trimmed.slice(0, 200)}` };
	}
}

export type TranscriptLine =
	| { kind: 'user'; text: string }
	| { kind: 'assistant'; text: string }
	| { kind: 'tool'; name: string; result: string }
	| { kind: 'system'; text: string };

/** Fold a stream of events into transcript lines. Tokens append to the
 *  last assistant line; tools and finals become their own lines. */
export function applyEvent(lines: TranscriptLine[], event: AgentEvent): TranscriptLine[] {
	switch (event.type) {
		case 'token': {
			const last = lines[lines.length - 1];
			if (last && last.kind === 'assistant') {
				return [...lines.slice(0, -1), { kind: 'assistant', text: last.text + event.text }];
			}
			return [...lines, { kind: 'assistant', text: event.text }];
		}
		case 'tool':
			return [...lines, { kind: 'tool', name: event.name, result: event.result }];
		case 'final': {
			const last = lines[lines.length - 1];
			// The final text is usually the already-streamed reply; do
			// not duplicate it verbatim as a second assistant line.
			if (last && last.kind === 'assistant' && last.text.trim() === event.text.trim()) {
				return lines;
			}
			return [...lines, { kind: 'assistant', text: event.text }];
		}
		case 'error':
			return [...lines, { kind: 'system', text: `error: ${event.message}` }];
		case 'session':
			return lines;
	}
}

export function toolStatusMark(result: string): string {
	const lower = result.toLowerCase();
	if (lower.includes('tool error') || lower.startsWith('refused') || lower.includes('refused:')) {
		return '✕';
	}
	return '✓';
}

export function truncate(text: string, max = 400): string {
	return text.length > max ? text.slice(0, max) + '…' : text;
}
