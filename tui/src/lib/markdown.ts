/** Minimal markdown-ish rendering for assistant replies.
 *
 * Only two inline constructs are handled, deliberately:
 * `code` (dimmed in the UI) and **bold**. Everything else is
 * left as plain text — this is not a full markdown renderer
 * and never claims to be. Headings/lists render as-is.
 */

export interface TextSegment {
	text: string;
	bold?: boolean;
	code?: boolean;
}

const TOKEN_RE = /(\*\*[^*]+\*\*|`[^`]+`)/g;

/** Split text into plain/bold/code segments, in order. */
export function parseMarkdownSegments(text: string): TextSegment[] {
	const segments: TextSegment[] = [];
	let last = 0;
	for (const match of text.matchAll(TOKEN_RE)) {
		const idx = match.index ?? 0;
		if (idx > last) segments.push({ text: text.slice(last, idx) });
		const token = match[0];
		if (token.startsWith('**')) {
			segments.push({ text: token.slice(2, -2), bold: true });
		} else {
			segments.push({ text: token.slice(1, -1), code: true });
		}
		last = idx + token.length;
	}
	if (last < text.length) segments.push({ text: text.slice(last) });
	if (segments.length === 0) segments.push({ text });
	return segments;
}
