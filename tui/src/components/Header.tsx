import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

export function Header(props: {
	theme: Theme;
	provider: string;
	model: string;
	sessionId: string;
	modeLabel: string;
	permissionMode: string;
	toolCount: number;
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
		<Box borderStyle="single" borderColor={t.border} paddingX={1} flexDirection="column">
			<Box flexDirection="row">
				<Text bold color={t.primary}>
					⬢ shadowcode
				</Text>
				<Text color={t.muted}> │ </Text>
				<Text color={t.assistant}>
					{props.provider} / {props.model || '(default)'}
				</Text>
				<Text color={t.muted}> │ </Text>
				<Text bold color={t.secondary}>
					{props.modeLabel}
				</Text>
				<Text color={t.muted}> ({props.permissionMode})</Text>
				<Text color={t.muted}> │ session {sessionShort}</Text>
				<Text color={t.muted}> │ tools {props.toolCount}</Text>
				<Text color={t.muted}> │ tokens — (not reported by core protocol)</Text>
			</Box>
			{props.browserUrl || props.browserTitle ? (
				<Text color={t.tool}>
					🌐 preview {props.browserDriver ?? 'agent'} · {props.browserTitle || props.browserUrl} · {health}
				</Text>
			) : null}
		</Box>
	);
}
