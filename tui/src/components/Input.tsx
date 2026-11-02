import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

/** Bottom composer (Design 1): a bordered input box — purple
 * border in the claude-dark theme, where theme.primary is
 * purple — with a `> ` prompt and a cursor block, clearly
 * separated from the transcript above it.
 */
export function Input(props: { value: string; theme: Theme; thinking: boolean }): React.ReactElement {
	const t = props.theme;
	return (
		<Box borderStyle="single" borderColor={t.primary} paddingX={1}>
			<Text bold color={t.secondary}>
				&gt;{' '}
			</Text>
			<Text color={t.assistant}>{props.value}</Text>
			<Text color={props.thinking ? t.muted : t.primary}>▋</Text>
			{props.thinking ? <Text color={t.muted}> (agent working…)</Text> : null}
		</Box>
	);
}
