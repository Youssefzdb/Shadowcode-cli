import { describe, expect, it } from 'vitest';
import { parseMarkdownSegments } from '../src/lib/markdown.js';

describe('markdown-ish segments', () => {
	it('keeps plain text as one segment', () => {
		expect(parseMarkdownSegments('hello world')).toEqual([{ text: 'hello world' }]);
	});

	it('splits **bold** and `code` in order, leaving the rest plain', () => {
		const segs = parseMarkdownSegments('run **list_dir** then `read_file` now');
		expect(segs).toEqual([
			{ text: 'run ' },
			{ text: 'list_dir', bold: true },
			{ text: ' then ' },
			{ text: 'read_file', code: true },
			{ text: ' now' },
		]);
	});
});
