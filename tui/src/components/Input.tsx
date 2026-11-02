import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

/** Bottom composer box with a mode chip, not a bare prompt line. */
export function Input(props: { value: string; theme: Theme; modeLabel: string; thinking: boolean }): React.ReactElement {
	const t = props.theme;
	return (
		<Box borderStyle="single" borderColor={t.primary} paddingX={1}>
			<Text bold color={t.secondary}>
				[{props.modeLabel}]
			</Text>
			<Text> </Text>
			<Text color={t.assistant}>{props.value}</Text>
			<Text color={props.thinking ? t.muted : t.primary}>▋</Text>
			{props.thinking ? <Text color={t.muted}> (agent working…)</Text> : null}
		</Box>
	);
}
