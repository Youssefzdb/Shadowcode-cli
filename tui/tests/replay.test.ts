import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { countClickDriven, countScroll, countTransitions, formatReplayEntries, healthHistoryLines, readSavedWatchLog, viaKind } from '../src/lib/replay.js';

describe('cycle 10 browser watch replay (TS TUI)', () => {
	it('formats both driver transitions, in order', () => {
		const lines = formatReplayEntries([
			{ time: '00:49:14', title: 'Example Domain', url: 'https://example.com/', driver: 'agent' },
			{ time: '00:49:14', title: 'Example Domain', url: 'https://example.com/', driver: 'user' },
			{ time: '00:49:17', title: 'Example Domains', url: 'https://www.iana.org/help/example-domains', driver: 'user' },
			{ time: '00:49:17', title: 'Example Domains', url: 'https://www.iana.org/help/example-domains', driver: 'agent' },
		]);
		expect(lines[0]).toContain('4 entries');
		expect(lines).toContain('  ↳ driver transition: agent -> user');
		expect(lines).toContain('  ↳ driver transition: user -> agent');
		expect(countTransitions([
			{ driver: 'agent' }, { driver: 'user' }, { driver: 'user' }, { driver: 'agent' },
		])).toBe(2);
	});
	it('reads the most recent saved watch log, and nothing when there is none', () => {
		const dir = mkdtempSync(path.join(tmpdir(), 'shadowcode-replay-'));
		mkdirSync(path.join(dir, '.shadowcode'), { recursive: true });
		writeFileSync(path.join(dir, '.shadowcode', 'browser-watch-20261102-004908-30363.json'), JSON.stringify([
			{ time: '00:49:14', title: 'Example Domain', url: 'https://example.com/', driver: 'agent' },
			{ time: '00:49:17', title: 'Example Domains', url: 'https://www.iana.org/help/example-domains', driver: 'user' },
		]));
		const saved = readSavedWatchLog(dir);
		expect(saved.file).toContain('browser-watch-20261102-004908-30363.json');
		expect(saved.entries).toHaveLength(2);
		expect(saved.entries[1]?.driver).toBe('user');
		const empty = readSavedWatchLog(path.join(dir, 'no-such-workdir'));
		expect(empty).toEqual({ file: null, entries: [] });
		expect(formatReplayEntries([])).toContain('  (no page changes observed yet)');
	});
	it('cycle 11: no-navigation takeover/handback still counts 2 transitions on the same page', () => {
		const entries = [
			{ time: '01:15:16', title: '', url: 'https://httpbin.org/html', driver: 'agent' },
			{ time: '01:15:16', title: '', url: 'https://httpbin.org/html', driver: 'user' },
			{ time: '01:15:18', title: '', url: 'https://httpbin.org/html', driver: 'agent' },
		];
		expect(countTransitions(entries)).toBe(2);
		expect(formatReplayEntries(entries)).toContain('  ↳ driver transition: agent -> user');
		expect(formatReplayEntries(entries)).toContain('  ↳ driver transition: user -> agent');
		// The panel header (BrowserWatchPanel) renders these same counts;
		// the count itself is what makes a same-page replay readable.
		expect(entries[0]?.url).toBe(entries[2]?.url);
	});
	it('health-history lines are the core output verbatim, never invented', () => {
		expect(healthHistoryLines('health history (newest first):\n  2026-11-02 provider=mock\n')).toEqual([
			'health history (newest first):',
			'  2026-11-02 provider=mock',
		]);
		expect(healthHistoryLines('')).toEqual(['health history: no output from the core']);
	});
});

describe('cycle 12 click-driven replay (TS TUI)', () => {
	it('marks preview-click entries [click-driven] and counts them', async () => {
		const mod = await import('../src/lib/replay.js');
		const entries = [
			{ time: '02:00:00', title: 'Internet Assigned Numbers Authority', url: 'https://www.iana.org/', driver: 'agent' },
			{ time: '02:00:01', title: 'Internet Assigned Numbers Authority', url: 'https://www.iana.org/', driver: 'user' },
			{ time: '02:00:05', title: 'Domain Names', url: 'https://www.iana.org/domains', driver: 'user', via: 'preview click (266,358)' },
			{ time: '02:00:06', title: 'Domain Names', url: 'https://www.iana.org/domains', driver: 'agent' },
		];
		const lines = mod.formatReplayEntries(entries);
		expect(lines.some((l) => l.includes('via preview click (266,358) [click-driven]'))).toBe(true);
		expect(mod.countClickDriven(entries)).toBe(1);
	});
});

describe('cycle 14 scroll_to + click_text replay (TS TUI)', () => {
	it('marks scroll_to [scroll] and click_text [click-driven], without cross-marking', () => {
		const entries = [
			{ time: '01:50:45', title: 'The GNU Operating System and the Free Software Movement', url: 'https://www.gnu.org/', driver: 'agent' },
			{ time: '01:50:45', title: 'The GNU Operating System and the Free Software Movement', url: 'https://www.gnu.org/', driver: 'user' },
			{ time: '01:50:47', title: 'The GNU Operating System and the Free Software Movement', url: 'https://www.gnu.org/', driver: 'user', via: 'preview scroll to text=Try GNU/Linux' },
			{ time: '01:50:50', title: 'List of Free GNU/Linux Distributions - GNU Project - Free Software Foundation', url: 'https://www.gnu.org/distros/free-distros.html', driver: 'user', via: 'preview click (Try GNU/Linux)' },
			{ time: '01:50:51', title: 'List of Free GNU/Linux Distributions - GNU Project - Free Software Foundation', url: 'https://www.gnu.org/distros/free-distros.html', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		expect(lines.some((l) => l.includes('via preview scroll to text=Try GNU/Linux [scroll]'))).toBe(true);
		expect(lines.some((l) => l.includes('via preview click (Try GNU/Linux) [click-driven]'))).toBe(true);
		const scrollLine = lines.find((l) => l.includes('preview scroll to')) ?? '';
		expect(scrollLine).not.toContain('[click-driven]');
		const clickLine = lines.find((l) => l.includes('preview click (Try GNU/Linux)')) ?? '';
		expect(clickLine).not.toContain('[scroll]');
		expect(countScroll(entries)).toBe(1);
	});
});

describe('cycle 15 CSS scroll_to + click_selector replay (TS TUI)', () => {
	it('marks scroll_to [scroll] and click_selector [click-driven], without cross-marking, even when the selector contains the other word', () => {
		expect(viaKind("preview click (#scroll-nav a)")).toBe('click');
		expect(viaKind('preview scroll to a.clickable')).toBe('scroll');
		expect(viaKind('preview goto')).toBe('');
		const entries = [
			{ time: '01:55:27', title: 'Debian -- The Universal Operating System', url: 'https://www.debian.org/', driver: 'agent' },
			{ time: '01:55:27', title: 'Debian -- The Universal Operating System', url: 'https://www.debian.org/', driver: 'user' },
			{ time: '01:55:27', title: 'Debian -- The Universal Operating System', url: 'https://www.debian.org/', driver: 'user', via: "preview scroll to a[href='intro/philosophy']" },
			{ time: '01:55:30', title: 'Debian -- Our Philosophy: Why we do it and how we do it', url: 'https://www.debian.org/intro/philosophy', driver: 'user', via: "preview click (a[href='intro/philosophy'])" },
			{ time: '01:55:30', title: 'Debian -- Our Philosophy: Why we do it and how we do it', url: 'https://www.debian.org/intro/philosophy', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='intro/philosophy'] [scroll]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='intro/philosophy']) [click-driven]"))).toBe(true);
		const scrollLine = lines.find((l) => l.includes('preview scroll to')) ?? '';
		expect(scrollLine).not.toContain('[click-driven]');
		const clickLine = lines.find((l) => l.includes("preview click (a[href")) ?? '';
		expect(clickLine).not.toContain('[scroll]');
		expect(countScroll(entries)).toBe(1);
		expect(countClickDriven(entries)).toBe(1);
		expect(countTransitions(entries)).toBe(2);
		const tricky = formatReplayEntries([
			{ time: '01:00:00', title: 'X', url: 'https://example.com/', driver: 'user', via: 'preview click (#scroll-nav a)' },
			{ time: '01:00:01', title: 'X', url: 'https://example.com/', driver: 'user', via: 'preview scroll to a.clickable' },
		]);
		const clickTricky = tricky.find((l) => l.includes('#scroll-nav')) ?? '';
		expect(clickTricky).toContain('[click-driven]');
		expect(clickTricky).not.toContain('[scroll]');
		const scrollTricky = tricky.find((l) => l.includes('a.clickable')) ?? '';
		expect(scrollTricky).toContain('[scroll]');
		expect(scrollTricky).not.toContain('[click-driven]');
	});
});

describe('cycle 16 distinct scroll + click selectors replay (TS TUI)', () => {
	it('shows two DIFFERENT selectors distinctly: scroll to /what/cli [scroll] only, click /what/wasm [click-driven] only, with both transitions', () => {
		expect(viaKind("preview scroll to a[href='/what/cli']")).toBe('scroll');
		expect(viaKind("preview click (a[href='/what/wasm'])")).toBe('click');
		const entries = [
			{ time: '03:07:44', title: 'Rust Programming Language', url: 'https://rust-lang.org/', driver: 'agent' },
			{ time: '03:07:44', title: 'Rust Programming Language', url: 'https://rust-lang.org/', driver: 'user' },
			{ time: '03:07:47', title: 'Rust Programming Language', url: 'https://rust-lang.org/', driver: 'user', via: "preview scroll to a[href='/what/cli']" },
			{ time: '03:07:49', title: 'WebAssembly - Rust Programming Language', url: 'https://rust-lang.org/what/wasm/', driver: 'user', via: "preview click (a[href='/what/wasm'])" },
			{ time: '03:07:50', title: 'WebAssembly - Rust Programming Language', url: 'https://rust-lang.org/what/wasm/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/what/cli'] [scroll]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/what/wasm']) [click-driven]"))).toBe(true);
		const scrollLine = lines.find((l) => l.includes('preview scroll to')) ?? '';
		expect(scrollLine).not.toContain('[click-driven]');
		expect(scrollLine).not.toContain('/what/wasm');
		const clickLine = lines.find((l) => l.includes("preview click (a[href")) ?? '';
		expect(clickLine).not.toContain('[scroll]');
		expect(clickLine).not.toContain('/what/cli');
		expect(countScroll(entries)).toBe(1);
		expect(countClickDriven(entries)).toBe(1);
		expect(countTransitions(entries)).toBe(2);
	});
});

describe('cycle 13 scroll replay (TS TUI)', () => {
	it('marks preview-scroll entries [scroll] and counts them, without click-marking them', () => {
		const entries = [
			{ time: '02:30:00', title: 'Welcome to Python.org', url: 'https://www.python.org/', driver: 'agent' },
			{ time: '02:30:01', title: 'Welcome to Python.org', url: 'https://www.python.org/', driver: 'user' },
			{ time: '02:30:02', title: 'Welcome to Python.org', url: 'https://www.python.org/', driver: 'user', via: 'preview scroll down' },
			{ time: '02:30:05', title: 'Python for Beginners', url: 'https://www.python.org/about/gettingstarted/', driver: 'user', via: 'preview click (181,536)' },
			{ time: '02:30:06', title: 'Python for Beginners', url: 'https://www.python.org/about/gettingstarted/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		expect(lines.some((l) => l.includes('via preview scroll down [scroll]'))).toBe(true);
		expect(lines.some((l) => l.includes('via preview click (181,536) [click-driven]'))).toBe(true);
		expect(countScroll(entries)).toBe(1);
	});
});

describe('cycle 17 multi-step replay (TS TUI)', () => {
	it('numbers scroll -> click -> scroll -> click as steps 1..4, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '03:42:58', title: 'Ruby Programming Language', url: 'https://www.ruby-lang.org/en/', driver: 'agent' },
			{ time: '03:42:58', title: 'Ruby Programming Language', url: 'https://www.ruby-lang.org/en/', driver: 'user' },
			{ time: '03:42:59', title: 'Ruby Programming Language', url: 'https://www.ruby-lang.org/en/', driver: 'user', via: "preview scroll to a[href='/en/news/2026/10/23/ruby-3-4-12-released/']" },
			{ time: '03:43:01', title: 'Security | Ruby', url: 'https://www.ruby-lang.org/en/security/', driver: 'user', via: "preview click (a[href='/en/security/'] >> nth=1)" },
			{ time: '03:43:02', title: 'Security | Ruby', url: 'https://www.ruby-lang.org/en/security/', driver: 'user', via: "preview scroll to a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/']" },
			{ time: '03:43:03', title: 'CVE-2024-49761: ReDoS vulnerability in REXML | Ruby', url: 'https://www.ruby-lang.org/en/news/2024/10/28/redos-rexml-cve-2024-49761/', driver: 'user', via: "preview click (a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/'])" },
			{ time: '03:43:03', title: 'CVE-2024-49761: ReDoS vulnerability in REXML | Ruby', url: 'https://www.ruby-lang.org/en/news/2024/10/28/redos-rexml-cve-2024-49761/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/en/news/2026/10/23/ruby-3-4-12-released/'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/en/security/'] >> nth=1) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 2 scroll, 2 click-driven, 2 driver transitions (4 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(2);
		expect(countClickDriven(entries)).toBe(2);
		expect(countTransitions(entries)).toBe(2);
		const plain = formatReplayEntries(entries.slice(0, 2));
		expect(plain.some((l) => l.includes('[step '))).toBe(false);
	});
});

describe('cycle 18 three-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click -> scroll -> click -> scroll -> click as steps 1..6, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '04:08:42', title: 'Home ⚡ Zig Programming Language', url: 'https://ziglang.org/', driver: 'agent' },
			{ time: '04:08:42', title: 'Home ⚡ Zig Programming Language', url: 'https://ziglang.org/', driver: 'user' },
			{ time: '04:08:43', title: 'Home ⚡ Zig Programming Language', url: 'https://ziglang.org/', driver: 'user', via: "preview scroll to a[href='/code-of-conduct/']" },
			{ time: '04:08:46', title: 'Zig Software Foundation ⚡ Zig Programming Language', url: 'https://ziglang.org/zsf/', driver: 'user', via: "preview click (a[href='/zsf/'] >> nth=2)" },
			{ time: '04:08:49', title: 'Zig Software Foundation ⚡ Zig Programming Language', url: 'https://ziglang.org/zsf/', driver: 'user', via: "preview scroll to a[href='/zsf/meeting-minutes/']" },
			{ time: '04:08:53', title: '2025 Financial Report and Fundraiser ⚡ Zig Programming Language', url: 'https://ziglang.org/news/2025-financials/', driver: 'user', via: "preview click (a[href='/news/2025-financials/'])" },
			{ time: '04:08:55', title: '2025 Financial Report and Fundraiser ⚡ Zig Programming Language', url: 'https://ziglang.org/news/2025-financials/', driver: 'user', via: "preview scroll to a[href='/zsf']" },
			{ time: '04:08:58', title: '300k USD Donation Pledged by Mitchell Hashimoto ⚡ Zig Programming Language', url: 'https://ziglang.org/news/300k-from-mitchellh/', driver: 'user', via: "preview click (a[href='/news/300k-from-mitchellh/'])" },
			{ time: '04:09:01', title: '300k USD Donation Pledged by Mitchell Hashimoto ⚡ Zig Programming Language', url: 'https://ziglang.org/news/300k-from-mitchellh/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/code-of-conduct/'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/zsf/'] >> nth=2) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/zsf/meeting-minutes/'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/news/2025-financials/']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/zsf'] [scroll] [step 5]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/news/300k-from-mitchellh/']) [click-driven] [step 6]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 3 scroll, 3 click-driven, 2 driver transitions (6 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(3);
		expect(countClickDriven(entries)).toBe(3);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 19 four-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x4 as steps 1..8, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '05:14:20', title: 'PHP', url: 'https://www.php.net/', driver: 'agent' },
			{ time: '05:14:21', title: 'PHP', url: 'https://www.php.net/', driver: 'user' },
			{ time: '05:14:22', title: 'PHP', url: 'https://www.php.net/', driver: 'user', via: "preview scroll to a[href='https://www.php.net/archive/2026.php#2026-10-21-4']" },
			{ time: '05:14:25', title: 'PHP: News Archive - 2026', url: 'https://www.php.net/archive/2026.php#2026-10-21-4', driver: 'user', via: "preview click (a[href='https://www.php.net/archive/2026.php#2026-10-21-4'])" },
			{ time: '05:14:25', title: 'PHP: News Archive - 2026', url: 'https://www.php.net/archive/2026.php#2026-10-21-4', driver: 'user', via: "preview scroll to a[href='https://www.php.net/ChangeLog-8.php#8.5.12']" },
			{ time: '05:14:29', title: 'PHP: PHP 8 ChangeLog', url: 'https://www.php.net/ChangeLog-8.php#8.5.12', driver: 'user', via: "preview click (a[href='https://www.php.net/ChangeLog-8.php#8.5.12'])" },
			{ time: '05:14:30', title: 'PHP: PHP 8 ChangeLog', url: 'https://www.php.net/ChangeLog-8.php#8.5.12', driver: 'user', via: "preview scroll to a[href='/sites.php']" },
			{ time: '05:14:33', title: "PHP: A Tourist's Guide", url: 'https://www.php.net/sites.php', driver: 'user', via: "preview click (a[href='/sites.php'])" },
			{ time: '05:14:34', title: "PHP: A Tourist's Guide", url: 'https://www.php.net/sites.php', driver: 'user', via: "preview scroll to a[href='/contact.php']" },
			{ time: '05:14:37', title: 'PHP: Contact', url: 'https://www.php.net/contact.php', driver: 'user', via: "preview click (a[href='/contact.php'])" },
			{ time: '05:14:37', title: 'PHP: Contact', url: 'https://www.php.net/contact.php', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='https://www.php.net/archive/2026.php#2026-10-21-4'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='https://www.php.net/archive/2026.php#2026-10-21-4']) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='https://www.php.net/ChangeLog-8.php#8.5.12'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='https://www.php.net/ChangeLog-8.php#8.5.12']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/sites.php'] [scroll] [step 5]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/sites.php']) [click-driven] [step 6]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/contact.php'] [scroll] [step 7]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/contact.php']) [click-driven] [step 8]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 4 scroll, 4 click-driven, 2 driver transitions (8 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(4);
		expect(countClickDriven(entries)).toBe(4);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 20 five-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x5 as steps 1..10, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '06:22:24', title: 'The Perl Programming Language - www.perl.org', url: 'https://www.perl.org/', driver: 'agent' },
			{ time: '06:22:24', title: 'The Perl Programming Language - www.perl.org', url: 'https://www.perl.org/', driver: 'user' },
			{ time: '06:22:25', title: 'The Perl Programming Language - www.perl.org', url: 'https://www.perl.org/', driver: 'user', via: "preview scroll to a[href='/contribute.html']" },
			{ time: '06:22:31', title: 'Contribute to Perl - www.perl.org', url: 'https://www.perl.org/contribute.html', driver: 'user', via: "preview click (a[href='/contribute.html'])" },
			{ time: '06:22:32', title: 'Contribute to Perl - www.perl.org', url: 'https://www.perl.org/contribute.html', driver: 'user', via: "preview scroll to a[href='/siteinfo.html']" },
			{ time: '06:22:35', title: 'Site Information - www.perl.org', url: 'https://www.perl.org/siteinfo.html', driver: 'user', via: "preview click (a[href='/siteinfo.html'])" },
			{ time: '06:22:37', title: 'Site Information - www.perl.org', url: 'https://www.perl.org/siteinfo.html', driver: 'user', via: "preview scroll to a[href='/about/whitepapers/']" },
			{ time: '06:22:40', title: 'Perl 5 White Papers - www.perl.org', url: 'https://www.perl.org/about/whitepapers/', driver: 'user', via: "preview click (a[href='/about/whitepapers/'])" },
			{ time: '06:22:42', title: 'Perl 5 White Papers - www.perl.org', url: 'https://www.perl.org/about/whitepapers/', driver: 'user', via: "preview scroll to a[href='/app.html']" },
			{ time: '06:22:45', title: 'Application Programming - www.perl.org', url: 'https://www.perl.org/app.html', driver: 'user', via: "preview click (a[href='/app.html'])" },
			{ time: '06:22:47', title: 'Application Programming - www.perl.org', url: 'https://www.perl.org/app.html', driver: 'user', via: "preview scroll to a[href='/about/style-guide.html']" },
			{ time: '06:22:50', title: 'Perl or perl? - www.perl.org', url: 'https://www.perl.org/about/style-guide.html', driver: 'user', via: "preview click (a[href='/about/style-guide.html'])" },
			{ time: '06:22:51', title: 'Perl or perl? - www.perl.org', url: 'https://www.perl.org/about/style-guide.html', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/contribute.html'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/contribute.html']) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/siteinfo.html'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/siteinfo.html']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/about/whitepapers/'] [scroll] [step 5]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/about/whitepapers/']) [click-driven] [step 6]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/app.html'] [scroll] [step 7]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/app.html']) [click-driven] [step 8]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/about/style-guide.html'] [scroll] [step 9]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/about/style-guide.html']) [click-driven] [step 10]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 5 scroll, 5 click-driven, 2 driver transitions (10 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(5);
		expect(countClickDriven(entries)).toBe(5);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 21 six-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x6 as steps 1..12, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '06:27:11', title: 'The Scala Programming Language', url: 'https://www.scala-lang.org/', driver: 'agent' },
			{ time: '06:27:12', title: 'The Scala Programming Language', url: 'https://www.scala-lang.org/', driver: 'user' },
			{ time: '06:27:12', title: 'The Scala Programming Language', url: 'https://www.scala-lang.org/', driver: 'user', via: "preview scroll to a[href='/conduct.html']" },
			{ time: '06:27:16', title: 'Loading https://www.scala-lang.org/conduct/', url: 'https://www.scala-lang.org/conduct.html', driver: 'user', via: "preview click (a[href='/conduct.html'])" },
			{ time: '06:27:18', title: 'The Scala Code of Conduct | The Scala Programming Language', url: 'https://www.scala-lang.org/conduct/', driver: 'user' },
			{ time: '06:27:18', title: 'The Scala Code of Conduct | The Scala Programming Language', url: 'https://www.scala-lang.org/conduct/', driver: 'user', via: "preview scroll to a[href='/license/']" },
			{ time: '06:27:21', title: 'Scala License | The Scala Programming Language', url: 'https://www.scala-lang.org/license/', driver: 'user', via: "preview click (a[href='/license/'])" },
			{ time: '06:27:22', title: 'Scala License | The Scala Programming Language', url: 'https://www.scala-lang.org/license/', driver: 'user', via: "preview scroll to a[href='/security/']" },
			{ time: '06:27:26', title: 'Scala Security Policy | The Scala Programming Language', url: 'https://www.scala-lang.org/security/', driver: 'user', via: "preview click (a[href='/security/'])" },
			{ time: '06:27:27', title: 'Scala Security Policy | The Scala Programming Language', url: 'https://www.scala-lang.org/security/', driver: 'user', via: "preview scroll to a[href='/governance/']" },
			{ time: '06:27:32', title: 'Governance | The Scala Programming Language', url: 'https://www.scala-lang.org/governance/', driver: 'user', via: "preview click (a[href='/governance/'])" },
			{ time: '06:27:32', title: 'Governance | The Scala Programming Language', url: 'https://www.scala-lang.org/governance/', driver: 'user', via: "preview scroll to a[href='/blog/']" },
			{ time: '06:27:36', title: 'Blog | The Scala Programming Language', url: 'https://www.scala-lang.org/blog/', driver: 'user', via: "preview click (a[href='/blog/'])" },
			{ time: '06:27:37', title: 'Blog | The Scala Programming Language', url: 'https://www.scala-lang.org/blog/', driver: 'user', via: "preview scroll to a[href='/download/']" },
			{ time: '06:27:42', title: 'Install | The Scala Programming Language', url: 'https://www.scala-lang.org/download/', driver: 'user', via: "preview click (a[href='/download/'])" },
			{ time: '06:27:42', title: 'Install | The Scala Programming Language', url: 'https://www.scala-lang.org/download/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/conduct.html'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/conduct.html']) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/license/'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/license/']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/security/'] [scroll] [step 5]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/security/']) [click-driven] [step 6]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/governance/'] [scroll] [step 7]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/governance/']) [click-driven] [step 8]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/blog/'] [scroll] [step 9]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/blog/']) [click-driven] [step 10]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/download/'] [scroll] [step 11]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/download/']) [click-driven] [step 12]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 6 scroll, 6 click-driven, 2 driver transitions (12 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(6);
		expect(countClickDriven(entries)).toBe(6);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 22 seven-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x7 as steps 1..14, with a steps footer, without cross-marking', () => {
		const entries = [
			{ time: '06:35:47', title: 'The Elixir programming language', url: 'https://elixir-lang.org/', driver: 'agent' },
			{ time: '06:35:47', title: 'The Elixir programming language', url: 'https://elixir-lang.org/', driver: 'user' },
			{ time: '06:35:47', title: 'The Elixir programming language', url: 'https://elixir-lang.org/', driver: 'user', via: "preview scroll to a[href='/install/']" },
			{ time: '06:35:51', title: 'Install Elixir | The Elixir programming language', url: 'https://elixir-lang.org/install/', driver: 'user', via: "preview click (a[href='/install/'])" },
			{ time: '06:35:52', title: 'Install Elixir | The Elixir programming language', url: 'https://elixir-lang.org/install/', driver: 'user', via: "preview scroll to a[href='/learning/']" },
			{ time: '06:35:57', title: 'Learning | The Elixir programming language', url: 'https://elixir-lang.org/learning/', driver: 'user', via: "preview click (a[href='/learning/'])" },
			{ time: '06:35:57', title: 'Learning | The Elixir programming language', url: 'https://elixir-lang.org/learning/', driver: 'user', via: "preview scroll to a[href='/docs/']" },
			{ time: '06:36:01', title: 'Documentation | The Elixir programming language', url: 'https://elixir-lang.org/docs/', driver: 'user', via: "preview click (a[href='/docs/'])" },
			{ time: '06:36:02', title: 'Documentation | The Elixir programming language', url: 'https://elixir-lang.org/docs/', driver: 'user', via: "preview scroll to a[href='/cases/']" },
			{ time: '06:36:07', title: 'Case studies | The Elixir programming language', url: 'https://elixir-lang.org/cases/', driver: 'user', via: "preview click (a[href='/cases/'])" },
			{ time: '06:36:07', title: 'Case studies | The Elixir programming language', url: 'https://elixir-lang.org/cases/', driver: 'user', via: "preview scroll to a[href='/blog/']" },
			{ time: '06:36:11', title: 'Blog | The Elixir programming language', url: 'https://elixir-lang.org/blog/', driver: 'user', via: "preview click (a[href='/blog/'])" },
			{ time: '06:36:12', title: 'Blog | The Elixir programming language', url: 'https://elixir-lang.org/blog/', driver: 'user', via: "preview scroll to a[href='/development/']" },
			{ time: '06:36:17', title: 'Development & team | The Elixir programming language', url: 'https://elixir-lang.org/development/', driver: 'user', via: "preview click (a[href='/development/'])" },
			{ time: '06:36:17', title: 'Development & team | The Elixir programming language', url: 'https://elixir-lang.org/development/', driver: 'user', via: "preview scroll to a[href='/trademarks/']" },
			{ time: '06:36:21', title: 'Trademarks policy | The Elixir programming language', url: 'https://elixir-lang.org/trademarks/', driver: 'user', via: "preview click (a[href='/trademarks/'])" },
			{ time: '06:36:22', title: 'Trademarks policy | The Elixir programming language', url: 'https://elixir-lang.org/trademarks/', driver: 'agent' },
		];
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14']);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/install/'] [scroll] [step 1]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/install/']) [click-driven] [step 2]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/learning/'] [scroll] [step 3]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/learning/']) [click-driven] [step 4]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/docs/'] [scroll] [step 5]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/docs/']) [click-driven] [step 6]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/cases/'] [scroll] [step 7]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/cases/']) [click-driven] [step 8]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/blog/'] [scroll] [step 9]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/blog/']) [click-driven] [step 10]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/development/'] [scroll] [step 11]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/development/']) [click-driven] [step 12]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview scroll to a[href='/trademarks/'] [scroll] [step 13]"))).toBe(true);
		expect(lines.some((l) => l.includes("via preview click (a[href='/trademarks/']) [click-driven] [step 14]"))).toBe(true);
		expect(lines.some((l) => l.includes('steps: 7 scroll, 7 click-driven, 2 driver transitions (14 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(7);
		expect(countClickDriven(entries)).toBe(7);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 23 eight-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x8 as steps 1..16, with a steps footer, without cross-marking', () => {
		const pages = [
			{ title: 'The Programming Language Lua', url: 'https://www.lua.org/', next: 'start.html' },
			{ title: 'Lua: getting started', url: 'https://www.lua.org/start.html', next: 'docs.html' },
			{ title: 'Lua: documentation', url: 'https://www.lua.org/docs.html', next: 'faq.html' },
			{ title: 'Lua: FAQ', url: 'https://www.lua.org/faq.html', next: 'versions.html' },
			{ title: 'Lua: version history', url: 'https://www.lua.org/versions.html', next: 'license.html' },
			{ title: 'Lua: license', url: 'https://www.lua.org/license.html', next: 'authors.html' },
			{ title: 'Lua: authors', url: 'https://www.lua.org/authors.html', next: 'thanks.html' },
			{ title: 'Lua: thanks', url: 'https://www.lua.org/thanks.html', next: 'donations.html' },
		];
		const entries: any[] = [
			{ time: '06:40:01', title: 'The Programming Language Lua', url: 'https://www.lua.org/', driver: 'agent' },
			{ time: '06:40:02', title: 'The Programming Language Lua', url: 'https://www.lua.org/', driver: 'user' },
		];
		for (const p of pages) {
			entries.push({ time: '06:40:02', title: p.title, url: p.url, driver: 'user', via: `preview scroll to a[href='${p.next}']` });
			const dest = pages.find((q) => q.url === `https://www.lua.org/${p.next}`);
			entries.push({ time: '06:40:04', title: dest ? dest.title : 'Lua: donations', url: `https://www.lua.org/${p.next}`, driver: 'user', via: `preview click (a[href='${p.next}'])` });
		}
		entries.push({ time: '06:40:29', title: 'Lua: donations', url: 'https://www.lua.org/donations.html', driver: 'agent' });
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']);
		for (const [i, sel] of ['start.html', 'docs.html', 'faq.html', 'versions.html', 'license.html', 'authors.html', 'thanks.html', 'donations.html'].entries()) {
			expect(lines.some((l) => l.includes(`via preview scroll to a[href='${sel}'] [scroll] [step ${2 * i + 1}]`))).toBe(true);
			expect(lines.some((l) => l.includes(`via preview click (a[href='${sel}']) [click-driven] [step ${2 * i + 2}]`))).toBe(true);
		}
		expect(lines.some((l) => l.includes('steps: 8 scroll, 8 click-driven, 2 driver transitions (16 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(8);
		expect(countClickDriven(entries)).toBe(8);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 24 nine-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x9 as steps 1..18, with a steps footer, without cross-marking', () => {
		const pages = [
			{ title: 'Welcome to a World of OCaml', url: 'https://ocaml.org/', next: '/docs', destTitle: 'Learn OCaml', destUrl: 'https://ocaml.org/docs' },
			{ title: 'Learn OCaml', url: 'https://ocaml.org/docs', next: '/tools', destTitle: 'OCaml Platform', destUrl: 'https://ocaml.org/platform' },
			{ title: 'OCaml Platform', url: 'https://ocaml.org/platform', next: '/packages', destTitle: 'OCaml Packages · Browse Community Packages', destUrl: 'https://ocaml.org/packages' },
			{ title: 'OCaml Packages · Browse Community Packages', url: 'https://ocaml.org/packages', next: '/community', destTitle: 'The OCaml Community', destUrl: 'https://ocaml.org/community' },
			{ title: 'The OCaml Community', url: 'https://ocaml.org/community', next: '/changelog', destTitle: 'OCaml Changelog', destUrl: 'https://ocaml.org/changelog' },
			{ title: 'OCaml Changelog', url: 'https://ocaml.org/changelog', next: '/events', destTitle: 'Upcoming OCaml Events', destUrl: 'https://ocaml.org/events' },
			{ title: 'Upcoming OCaml Events', url: 'https://ocaml.org/events', next: '/jobs', destTitle: 'OCaml Jobs', destUrl: 'https://ocaml.org/jobs' },
			{ title: 'OCaml Jobs', url: 'https://ocaml.org/jobs', next: '/security', destTitle: 'OCaml Security', destUrl: 'https://ocaml.org/security' },
			{ title: 'OCaml Security', url: 'https://ocaml.org/security', next: '/governance', destTitle: 'Governance', destUrl: 'https://ocaml.org/governance' },
		];
		const entries: any[] = [
			{ time: '06:52:31', title: 'Welcome to a World of OCaml', url: 'https://ocaml.org/', driver: 'agent' },
			{ time: '06:52:31', title: 'Welcome to a World of OCaml', url: 'https://ocaml.org/', driver: 'user' },
		];
		for (const p of pages) {
			entries.push({ time: '06:52:31', title: p.title, url: p.url, driver: 'user', via: `preview scroll to a[href='${p.next}']` });
			entries.push({ time: '06:52:34', title: p.destTitle, url: p.destUrl, driver: 'user', via: `preview click (a[href='${p.next}'])` });
		}
		entries.push({ time: '06:53:02', title: 'Governance', url: 'https://ocaml.org/governance', driver: 'agent' });
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18']);
		for (const [i, sel] of ['/docs', '/tools', '/packages', '/community', '/changelog', '/events', '/jobs', '/security', '/governance'].entries()) {
			expect(lines.some((l) => l.includes(`via preview scroll to a[href='${sel}'] [scroll] [step ${2 * i + 1}]`))).toBe(true);
			expect(lines.some((l) => l.includes(`via preview click (a[href='${sel}']) [click-driven] [step ${2 * i + 2}]`))).toBe(true);
		}
		expect(lines.some((l) => l.includes('steps: 9 scroll, 9 click-driven, 2 driver transitions (18 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(9);
		expect(countClickDriven(entries)).toBe(9);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 25 ten-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x10 as steps 1..20, with a steps footer, without cross-marking', () => {
		const pages = [
			{ title: 'The Julia Programming Language', url: 'https://julialang.org/', next: '/downloads/', destTitle: 'Installing Julia', destUrl: 'https://julialang.org/downloads/' },
			{ title: 'Installing Julia', url: 'https://julialang.org/downloads/', next: '/learning/', destTitle: 'Get started with Julia', destUrl: 'https://julialang.org/learning/' },
			{ title: 'Get started with Julia', url: 'https://julialang.org/learning/', next: '/blog/', destTitle: 'The Julia Language Blog', destUrl: 'https://julialang.org/blog/' },
			{ title: 'The Julia Language Blog', url: 'https://julialang.org/blog/', next: '/community/', destTitle: 'Community', destUrl: 'https://julialang.org/community/' },
			{ title: 'Community', url: 'https://julialang.org/community/', next: '/contribute/', destTitle: 'Ask and answer questions', destUrl: 'https://julialang.org/contribute/' },
			{ title: 'Ask and answer questions', url: 'https://julialang.org/contribute/', next: '/jsoc/', destTitle: 'Julia Seasons of Contributions', destUrl: 'https://julialang.org/jsoc/' },
			{ title: 'Julia Seasons of Contributions', url: 'https://julialang.org/jsoc/', next: '/community/standards/', destTitle: 'Julia Community - Standards', destUrl: 'https://julialang.org/community/standards/' },
			{ title: 'Julia Community - Standards', url: 'https://julialang.org/community/standards/', next: '/community/stewards/', destTitle: 'Julia Community - Stewards', destUrl: 'https://julialang.org/community/stewards/' },
			{ title: 'Julia Community - Stewards', url: 'https://julialang.org/community/stewards/', next: '/governance/', destTitle: 'Julia Governance', destUrl: 'https://julialang.org/governance/' },
			{ title: 'Julia Governance', url: 'https://julialang.org/governance/', next: '/diversity/', destTitle: 'Diversity', destUrl: 'https://julialang.org/diversity/' },
		];
		const entries: any[] = [
			{ time: '07:06:53', title: 'The Julia Programming Language', url: 'https://julialang.org/', driver: 'agent' },
			{ time: '07:06:53', title: 'The Julia Programming Language', url: 'https://julialang.org/', driver: 'user' },
		];
		for (const p of pages) {
			entries.push({ time: '07:06:54', title: p.title, url: p.url, driver: 'user', via: `preview scroll to a[href='${p.next}']` });
			entries.push({ time: '07:06:57', title: p.destTitle, url: p.destUrl, driver: 'user', via: `preview click (a[href='${p.next}'])` });
		}
		entries.push({ time: '07:07:30', title: 'Diversity', url: 'https://julialang.org/diversity/', driver: 'agent' });
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20']);
		for (const [i, sel] of ['/downloads/', '/learning/', '/blog/', '/community/', '/contribute/', '/jsoc/', '/community/standards/', '/community/stewards/', '/governance/', '/diversity/'].entries()) {
			expect(lines.some((l) => l.includes(`via preview scroll to a[href='${sel}'] [scroll] [step ${2 * i + 1}]`))).toBe(true);
			expect(lines.some((l) => l.includes(`via preview click (a[href='${sel}']) [click-driven] [step ${2 * i + 2}]`))).toBe(true);
		}
		expect(lines.some((l) => l.includes('steps: 10 scroll, 10 click-driven, 2 driver transitions (20 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(10);
		expect(countClickDriven(entries)).toBe(10);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 26 eleven-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x11 as steps 1..22, with a steps footer, without cross-marking', () => {
		const pages = [
			{ title: 'The Crystal Programming Language', url: 'https://crystal-lang.org/', next: '/install/', destTitle: 'Install - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/install/' },
			{ title: 'Install - The Crystal Programming Language', url: 'https://crystal-lang.org/install/', next: '/blog/', destTitle: 'News - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/blog/' },
			{ title: 'News - The Crystal Programming Language', url: 'https://crystal-lang.org/blog/', next: '/releases/', destTitle: 'Releases - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/releases/' },
			{ title: 'Releases - The Crystal Programming Language', url: 'https://crystal-lang.org/releases/', next: '/community/', destTitle: 'Community - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/community/' },
			{ title: 'Community - The Crystal Programming Language', url: 'https://crystal-lang.org/community/', next: '/sponsors/', destTitle: 'Sponsors - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/sponsors/' },
			{ title: 'Sponsors - The Crystal Programming Language', url: 'https://crystal-lang.org/sponsors/', next: '/success-stories/', destTitle: 'Success stories - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/success-stories/' },
			{ title: 'Success stories - The Crystal Programming Language', url: 'https://crystal-lang.org/success-stories/', next: '/used_in_prod/', destTitle: 'Used in production - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/used_in_prod/' },
			{ title: 'Used in production - The Crystal Programming Language', url: 'https://crystal-lang.org/used_in_prod/', next: '/team/', destTitle: 'Team - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/team/' },
			{ title: 'Team - The Crystal Programming Language', url: 'https://crystal-lang.org/team/', next: '/community/governance/', destTitle: 'Crystal governance - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/community/governance/' },
			{ title: 'Crystal governance - The Crystal Programming Language', url: 'https://crystal-lang.org/community/governance/', next: '/media/', destTitle: 'Media - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/media/' },
			{ title: 'Media - The Crystal Programming Language', url: 'https://crystal-lang.org/media/', next: '/learning/', destTitle: 'External resources - The Crystal Programming Language', destUrl: 'https://crystal-lang.org/learning/' },
		];
		const entries: any[] = [
			{ time: '07:14:51', title: 'The Crystal Programming Language', url: 'https://crystal-lang.org/', driver: 'agent' },
			{ time: '07:14:52', title: 'The Crystal Programming Language', url: 'https://crystal-lang.org/', driver: 'user' },
		];
		for (const p of pages) {
			entries.push({ time: '07:14:52', title: p.title, url: p.url, driver: 'user', via: `preview scroll to a[href='${p.next}']` });
			entries.push({ time: '07:14:56', title: p.destTitle, url: p.destUrl, driver: 'user', via: `preview click (a[href='${p.next}'])` });
		}
		entries.push({ time: '07:15:30', title: 'External resources - The Crystal Programming Language', url: 'https://crystal-lang.org/learning/', driver: 'agent' });
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22']);
		for (const [i, sel] of ['/install/', '/blog/', '/releases/', '/community/', '/sponsors/', '/success-stories/', '/used_in_prod/', '/team/', '/community/governance/', '/media/', '/learning/'].entries()) {
			expect(lines.some((l) => l.includes(`via preview scroll to a[href='${sel}'] [scroll] [step ${2 * i + 1}]`))).toBe(true);
			expect(lines.some((l) => l.includes(`via preview click (a[href='${sel}']) [click-driven] [step ${2 * i + 2}]`))).toBe(true);
		}
		expect(lines.some((l) => l.includes('steps: 11 scroll, 11 click-driven, 2 driver transitions (22 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(11);
		expect(countClickDriven(entries)).toBe(11);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});

describe('cycle 27 twelve-page chain replay (TS TUI)', () => {
	it('numbers scroll -> click x12 as steps 1..24, with a steps footer, without cross-marking', () => {
		const pages = [
			{ title: 'Clojure', url: 'https://clojure.org/', next: '/about/rationale', destTitle: 'Clojure - Rationale', destUrl: 'https://clojure.org/about/rationale' },
			{ title: 'Clojure - Rationale', url: 'https://clojure.org/about/rationale', next: '/reference/documentation', destTitle: 'Clojure - The Reader', destUrl: 'https://clojure.org/reference/reader' },
			{ title: 'Clojure - The Reader', url: 'https://clojure.org/reference/reader', next: '/api/api', destTitle: 'Clojure - API Documentation', destUrl: 'https://clojure.org/api/api' },
			{ title: 'Clojure - API Documentation', url: 'https://clojure.org/api/api', next: '/releases/downloads', destTitle: 'Clojure - Clojure Downloads', destUrl: 'https://clojure.org/releases/downloads' },
			{ title: 'Clojure - Clojure Downloads', url: 'https://clojure.org/releases/downloads', next: '/guides/guides', destTitle: 'Clojure - Getting Started', destUrl: 'https://clojure.org/guides/getting_started' },
			{ title: 'Clojure - Getting Started', url: 'https://clojure.org/guides/getting_started', next: '/community/success_stories', destTitle: 'Clojure - Success Stories', destUrl: 'https://clojure.org/community/success_stories' },
			{ title: 'Clojure - Success Stories', url: 'https://clojure.org/community/success_stories', next: '/dev/dev', destTitle: 'Clojure - Development', destUrl: 'https://clojure.org/dev/dev' },
			{ title: 'Clojure - Development', url: 'https://clojure.org/dev/dev', next: '/news/news', destTitle: 'Clojure - News', destUrl: 'https://clojure.org/news/news' },
			{ title: 'Clojure - News', url: 'https://clojure.org/news/news', next: '/community/resources', destTitle: 'Clojure - Community Resources', destUrl: 'https://clojure.org/community/resources' },
			{ title: 'Clojure - Community Resources', url: 'https://clojure.org/community/resources', next: '/community/contributing', destTitle: 'Clojure - Contributing', destUrl: 'https://clojure.org/community/contributing' },
			{ title: 'Clojure - Contributing', url: 'https://clojure.org/community/contributing', next: '/community/companies', destTitle: 'Clojure - Companies', destUrl: 'https://clojure.org/community/companies' },
			{ title: 'Clojure - Companies', url: 'https://clojure.org/community/companies', next: '/community/license', destTitle: 'Clojure - License', destUrl: 'https://clojure.org/community/license' },
		];
		const entries: any[] = [
			{ time: '07:22:05', title: 'Clojure', url: 'https://clojure.org/', driver: 'agent' },
			{ time: '07:22:05', title: 'Clojure', url: 'https://clojure.org/', driver: 'user' },
		];
		for (const p of pages) {
			entries.push({ time: '07:22:06', title: p.title, url: p.url, driver: 'user', via: `preview scroll to a[href='${p.next}']` });
			entries.push({ time: '07:22:10', title: p.destTitle, url: p.destUrl, driver: 'user', via: `preview click (a[href='${p.next}'])` });
		}
		entries.push({ time: '07:22:45', title: 'Clojure - License', url: 'https://clojure.org/community/license', driver: 'agent' });
		const lines = formatReplayEntries(entries);
		const stepLines = lines.filter((l) => l.includes('[step '));
		expect(stepLines.map((l) => l.split('[step ')[1]?.split(']')[0])).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']);
		for (const [i, sel] of ['/about/rationale', '/reference/documentation', '/api/api', '/releases/downloads', '/guides/guides', '/community/success_stories', '/dev/dev', '/news/news', '/community/resources', '/community/contributing', '/community/companies', '/community/license'].entries()) {
			expect(lines.some((l) => l.includes(`via preview scroll to a[href='${sel}'] [scroll] [step ${2 * i + 1}]`))).toBe(true);
			expect(lines.some((l) => l.includes(`via preview click (a[href='${sel}']) [click-driven] [step ${2 * i + 2}]`))).toBe(true);
		}
		expect(lines.some((l) => l.includes('steps: 12 scroll, 12 click-driven, 2 driver transitions (24 action steps)'))).toBe(true);
		expect(countScroll(entries)).toBe(12);
		expect(countClickDriven(entries)).toBe(12);
		expect(countTransitions(entries)).toBe(2);
		for (const l of stepLines) {
			if (l.includes('[scroll]')) expect(l.includes('[click-driven]')).toBe(false);
			if (l.includes('[click-driven]')) expect(l.includes('[scroll]')).toBe(false);
		}
	});
});
