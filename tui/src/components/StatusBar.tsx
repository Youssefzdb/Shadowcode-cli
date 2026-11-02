import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

export function StatusBar(props: {
	theme: Theme;
	status: string;
	thinking: boolean;
	spinner: string;
	toolCount: number;
	lastTool: string;
	messageCount: number;
	modeLabel: string;
	previewHealthy?: boolean | null;
	previewPort?: number;
	previewDriver?: string;
	previewTitle?: string;
	previewUrl?: string;
}): React.ReactElement {
	const t = props.theme;
	const preview =
		props.previewHealthy === null || props.previewHealthy === undefined
			? 'preview=unknown'
			: `preview localhost:${props.previewPort ?? 8765} ${props.previewHealthy ? 'healthy' : 'unavailable'} driver=${props.previewDriver ?? 'agent'}`;
	const page = props.previewTitle || props.previewUrl ? ` page=${(props.previewTitle || props.previewUrl || '').slice(0, 40)}` : '';
	return (
		<Box borderStyle="single" borderColor={t.border} paddingX={1}>
			<Text>
				<Text bold color={props.thinking ? t.primary : t.success}>
					{props.thinking ? `${props.spinner} thinking` : props.status}
				</Text>
				<Text color={t.muted}>
					{' '}
					│ mode {props.modeLabel} │ msgs={props.messageCount} tools={props.toolCount}
					{props.lastTool ? ` last=${props.lastTool}` : ''} │ {preview}
					{page} │ Ctrl+P palette · /help · Ctrl+T panel
				</Text>
			</Text>
		</Box>
	);
}
