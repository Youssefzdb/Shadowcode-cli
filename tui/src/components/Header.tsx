import React from 'react';
import { Box, Text } from 'ink';

export function Header(props: {
	provider: string;
	model: string;
	sessionId: string;
	permissionMode: string;
	browserUrl?: string;
	browserDriver?: string;
	browserTitle?: string;
	browserHealth?: boolean | null;
}): React.ReactElement {
	const health =
		props.browserHealth === null || props.browserHealth === undefined
			? 'unknown'
			: props.browserHealth
				? 'healthy'
				: 'unavailable';
	return (
		<Box borderStyle="round" borderColor="cyan" paddingX={1} flexDirection="column">
			<Text bold color="cyan">
				Shadowcode
			</Text>
			<Text>
				provider={props.provider} model={props.model || '(default)'} session={props.sessionId || '—'} perm=
				{props.permissionMode}
			</Text>
			{props.browserUrl ? (
				<Text color="magenta">
					browser preview: {props.browserUrl} ({props.browserDriver ?? 'agent'}) health={health}
				</Text>
			) : null}
			{props.browserTitle ? (
				<Text color="magenta">
					browser page: {props.browserTitle}
				</Text>
			) : null}
		</Box>
	);
}
