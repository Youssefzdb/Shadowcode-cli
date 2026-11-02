import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

/** Claude-style header (Design 1, user-chosen mockup), Shadowcode
 * branding only — no other product's name, logo, or source.
 *
 * Line 1: large wordmark. Line 2: model • version • session •
 * cwd, all on one line. Tokens/cost are deliberately NOT shown:
 * the JSON-lines protocol reports no token/cost fields, so any
 * number here would be invented. A browser-preview line appears
 * only when a preview actually exists.
 */
export function Header(props: {
	theme: Theme;
	provider: string;
	model: string;
	version?: string;
	sessionId: string;
	modeLabel: string;
	permissionMode: string;
	toolCount: number;
	cwd: string;
	browserUrl?: string;
	browserDriver?: string;
	browserTitle?: string;
	browserHealth?: boolean | null;
}): React.ReactElement {
	const t = props.theme;
	const health =
		props.browserHealth === null || props.browserHealth === undefined
			? 'unknown'
			: props.browserHealth
				? 'healthy'
				: 'unavailable';
	const sessionShort = props.sessionId ? props.sessionId.slice(0, 12) : '—';
	return (
		<Box flexDirection="column" paddingX={1}>
			<Text bold color={t.primary}>
				⬢ SHADOWCODE
			</Text>
			<Box flexDirection="row">
				<Text color={t.muted}>• </Text>
				<Text color={t.secondary}>
					{props.provider} / {props.model || '(default)'}
				</Text>
				{props.version ? (
					<Text color={t.muted}> • v{props.version}</Text>
				) : null}
				<Text color={t.muted}> • session: {sessionShort}</Text>
				<Text color={t.muted}> • {props.cwd}</Text>
				<Text color={t.muted}> • tools {props.toolCount}</Text>
				<Text color={t.muted}> • tokens —</Text>
			</Box>
			{props.browserUrl || props.browserTitle ? (
				<Text color={t.tool}>
					🌐 preview {props.browserDriver ?? 'agent'} · {props.browserTitle || props.browserUrl} · {health}
				</Text>
			) : null}
		</Box>
	);
}
