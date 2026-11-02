import { describe, expect, it } from 'vitest';
import { formatGoHits, goBinaryExists, goServerHealthy, searchGo } from '../src/lib/goSearch.js';
import { coreDoctor } from '../src/lib/coreCli.js';

describe('go search (cycle 6, optional backend)', () => {
	it('formats hits in the Python search shape', () => {
		expect(formatGoHits([{ path: 'a.txt', line: 2, text: 'hi', matches: 1 }])).toBe('a.txt:2: hi');
		expect(formatGoHits([])).toBe('no matches (Go search)');
	});
	it('returns null when no Go server is running (fallback, not fake hits)', async () => {
		// Port 1 is not a Go server; fetch must fail fast, not hang.
		await expect(searchGo(1, 'shadowcode')).resolves.toBeNull();
		await expect(goServerHealthy(1)).resolves.toBe(false);
	});
	it('does not claim a Go binary exists when it was not built', () => {
		// tui/ dir is passed, so goBinaryPath resolves to go/shadowcode-preview.
		// In this environment that file does not exist (no Go toolchain).
		expect(goBinaryExists(new URL('..', import.meta.url).pathname)).toBe(false);
	});
	it('core doctor runs via the Python core and mentions Shadowcode', () => {
		const r = coreDoctor(new URL('../../main.py', import.meta.url).pathname);
		expect(r.ok).toBe(true);
		expect(r.output).toContain('Shadowcode');
	});
});

describe('cycle 8 browser panel + health', () => {
	it('formats a browser panel with takeover/handback hints and watch tail', async () => {
		const mod = await import('../src/lib/goSearch.js');
		const panel = mod.formatBrowserPanel(
			{
				healthy: true,
				title: 'Example Domains',
				url: 'https://www.iana.org/help/example-domains',
				driver: 'user',
				hasScreenshot: true,
				watch: [
					{ time: '01:00:00', title: 'Example Domain', url: 'https://example.com/', driver: 'agent' },
					{ time: '01:01:00', title: 'Example Domains', url: 'https://www.iana.org/help/example-domains', driver: 'user' },
				],
				lastControlError: '',
			},
			8765,
		);
		expect(panel).toContain('Take control');
		expect(panel).toContain('Hand back to agent');
		expect(panel).toContain('no reload');
		expect(panel).toContain('Example Domains');
		expect(panel).toContain('01:01:00');
		const empty = mod.formatBrowserPanel(
			{ healthy: false, title: '', url: '', driver: '', hasScreenshot: false, watch: [], lastControlError: '' },
			8765,
		);
		expect(empty).toContain('not started');
	});
	it('core health runs via the Python core and mentions every component', async () => {
		const mod = await import('../src/lib/coreCli.js');
		const r = mod.coreHealth(new URL('../../main.py', import.meta.url).pathname);
		expect(r.ok).toBe(true);
		expect(r.output).toContain('python core');
		expect(r.output).toContain('typescript tui');
		expect(r.output).toContain('go preview');
		expect(r.output).toContain('native scanner');
		expect(r.output).toContain('playwright');
	});
});

describe('cycle 9 core CLI wiring', () => {
	it('health-history and browser-watch run via real core flags', async () => {
		const mod = await import('../src/lib/coreCli.js');
		const core = new URL('../../main.py', import.meta.url).pathname;
		const work = new URL('../../test-workspace', import.meta.url).pathname;
		const hist = mod.coreHealthHistory(core, work, 5);
		expect(hist.ok).toBe(true);
		expect(hist.output).toContain('health history');
		const watch = mod.coreBrowserWatch(core, work);
		expect(watch.ok).toBe(true);
		expect(watch.output).toContain('browser watch replay');
	});
});

describe('cycle 7 core CLI wiring', () => {
	it('lists sessions and session info via real core flags', async () => {
		const mod = await import('../src/lib/coreCli.js');
		const list = mod.coreListSessions(new URL('../../main.py', import.meta.url).pathname);
		expect(list.ok).toBe(true);
		expect(list.output.length).toBeGreaterThan(0);
		const info = mod.coreSessionInfo(new URL('../../main.py', import.meta.url).pathname, 'definitely-not-a-session');
		expect(info.output).toContain('failed');
	});
	it('preview state reports unavailable when no server runs', async () => {
		const mod = await import('../src/lib/goSearch.js');
		const st = await mod.fetchPreviewState(1);
		expect(st.healthy).toBe(false);
		expect(st.url).toBe('');
	});
	it('core search-files finds a file in the test workspace', async () => {
		const mod = await import('../src/lib/coreCli.js');
		const r = mod.coreSearchFiles(
			new URL('../../main.py', import.meta.url).pathname,
			new URL('../../test-workspace', import.meta.url).pathname,
			'shadowcode',
		);
		expect(r.ok).toBe(true);
		expect(r.output).toContain('hello.txt');
	});
});
