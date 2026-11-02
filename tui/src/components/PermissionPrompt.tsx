import React from 'react';
import { Box, Text, useInput } from 'ink';
import type { Theme } from '../lib/theme.js';

export function PermissionPrompt(props: {
	prompt: string;
	onAnswer: (allowed: boolean) => void;
	theme?: Theme;
}): React.ReactElement {
	const t = props.theme;
	useInput((_input, key) => {
		if (key.return) return;
	});
	return (
		<Box borderStyle="double" borderColor={t?.error ?? 'red'} paddingX={1} flexDirection="column">
			<Text bold color={t?.error ?? 'red'}>
				Permission required
			</Text>
			<Text>{props.prompt}</Text>
			<Text color={t?.muted ?? 'gray'}>Press y to allow, n to deny. In subprocess mode destructive tools are denied unless --allow-destructive was passed.</Text>
		</Box>
	);
}
