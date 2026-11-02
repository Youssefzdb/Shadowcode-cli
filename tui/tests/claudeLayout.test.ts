import { describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { parseGitHead, readGitBranch } from '../src/lib/git.js';
import { autoAcceptLabel } from '../src/lib/mode.js';
import { toolCardBorderColor, toolDisplayName, toolLineStatus } from '../src/lib/toolCards.js';
import { THEMES, resolveTheme } from '../src/lib/theme.js';

describe('claude-dark theme (Design 1)', () => {
	it('exists, is the new default palette, and differs from dark', () => {
		const t = resolveTheme('claude-dark');
		expect(t.name).toBe('claude-dark');
		expect(t.primary).toBe('#a78bfa');
		expect(t.secondary).toBe('#67e8f9');
		expect(t.primary).not.toBe(THEMES.dark?.primary);
		for (const field of ['primary', 'secondary', 'success', 'warning', 'error', 'muted', 'user', 'assistant', 'system', 'tool', 'border'] as const) {
			expect(t[field]).toMatch(/^#[0-9a-f]{6}$/i);
		}
	});
});

describe('git branch parsing (status bar)', () => {
	it('parses a normal ref HEAD', () => {
		expect(parseGitHead('ref: refs/heads/main\n')).toBe('main');
		expect(parseGitHead('ref: refs/heads/feature/tui-redesign')).toBe('feature/tui-redesign');
	});

	it('returns null for detached HEAD and garbage', () => {
		expect(parseGitHead('a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n')).toBeNull();
		expect(parseGitHead('')).toBeNull();
		expect(parseGitHead('not a head')).toBeNull();
	});

	it('reads .git/HEAD from a real directory, and null when not a repo', () => {
		const repo = mkdtempSync(path.join(tmpdir(), 'shadowcode-git-'));
		try {
			mkdirSync(path.join(repo, '.git'));
			writeFileSync(path.join(repo, '.git', 'HEAD'), 'ref: refs/heads/dev\n');
			expect(readGitBranch(repo)).toBe('dev');
			const plain = mkdtempSync(path.join(tmpdir(), 'shadowcode-nogit-'));
			try {
				expect(readGitBranch(plain)).toBeNull();
			} finally {
				rmSync(plain, { recursive: true, force: true });
			}
		} finally {
			rmSync(repo, { recursive: true, force: true });
		}
	});

	it('follows a worktree gitdir pointer file', () => {
		const repo = mkdtempSync(path.join(tmpdir(), 'shadowcode-wt-'));
		const realGit = mkdtempSync(path.join(tmpdir(), 'shadowcode-realgit-'));
		try {
			writeFileSync(path.join(realGit, 'HEAD'), 'ref: refs/heads/worktree-branch\n');
			writeFileSync(path.join(repo, '.git'), `gitdir: ${realGit}\n`);
			expect(readGitBranch(repo)).toBe('worktree-branch');
		} finally {
			rmSync(repo, { recursive: true, force: true });
			rmSync(realGit, { recursive: true, force: true });
		}
	});
});

describe('permission label mapping (status bar)', () => {
	it('never claims auto-accept on unless the flag is really set', () => {
		expect(autoAcceptLabel('plan', false)).toContain('off');
		expect(autoAcceptLabel('plan', true)).toContain('off');
		expect(autoAcceptLabel('manual', false)).toContain('ask');
		expect(autoAcceptLabel('auto', false)).toContain('guarded');
		expect(autoAcceptLabel('auto', true)).toContain('on');
	});
});

describe('tool card display (transcript cards + sidebar)', () => {
	it('titles write/edit from the path in the result, and never invents a read target', () => {
		expect(toolDisplayName('write_file', 'wrote /home/u/project/utils.py (120 chars)')).toBe('Write file: utils.py');
		expect(toolDisplayName('edit_file', 'edited /home/u/project/utils.py')).toBe('Edit file: utils.py');
		expect(toolDisplayName('diff_edit', 'diff for /home/u/project/utils.py (not applied):\n--- a/utils.py')).toBe('Diff: utils.py');
		// read_file result is file CONTENT, not a path: no target claimed.
		expect(toolDisplayName('read_file', 'def hello():\n    pass\n')).toBe('Read file');
		expect(toolDisplayName('run_shell', 'ok\n')).toBe('Run shell');
		expect(toolDisplayName('some_new_tool', 'x')).toBe('Some new tool');
	});

	it('maps status to border colours: done green, running yellow, failed red', () => {
		const theme = { success: '#00ff00', warning: '#ffff00', error: '#ff0000' };
		expect(toolCardBorderColor('done', theme)).toBe('#00ff00');
		expect(toolCardBorderColor('running', theme)).toBe('#ffff00');
		expect(toolCardBorderColor('failed', theme)).toBe('#ff0000');
	});

	it('derives failed only from real refusal/error results', () => {
		expect(toolLineStatus('tool error: boom')).toBe('failed');
		expect(toolLineStatus('refused: destructive command')).toBe('failed');
		expect(toolLineStatus('wrote /tmp/x.txt (5 chars)')).toBe('done');
	});
});
