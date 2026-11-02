import React from 'react';
import { Box, Text } from 'ink';

export function StatusBar(props: {
	status: string;
	thinking: boolean;
	toolCount: number;
	lastTool: string;
	messageCount: number;
	previewHealthy?: boolean | null;
	previewPort?: number;
	previewDriver?: string;
	previewTitle?: string;
	previewUrl?: string;
}): React.ReactElement {
	const preview =
		props.previewHealthy === null || props.previewHealthy === undefined
			? 'preview=unknown'
			: `preview localhost:${props.previewPort ?? 8765} ${props.previewHealthy ? 'healthy' : 'unavailable'} driver=${props.previewDriver ?? 'agent'}`;
	const page = props.previewTitle || props.previewUrl ? ` page=${(props.previewTitle || props.previewUrl || '').slice(0, 40)}` : '';
	return (
		<Box borderStyle="single" borderColor="gray" paddingX={1}>
			<Text>
				{props.thinking ? 'THINKING…' : props.status} | msgs={props.messageCount} tools={props.toolCount}
				{props.lastTool ? ` last=${props.lastTool}` : ''} | {preview}
				{page} | /help /exit !cmd = shell
			</Text>
		</Box>
	);
}
