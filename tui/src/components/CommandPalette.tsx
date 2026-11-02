import React from 'react';
import { Box, Text } from 'ink';
import type { CommandDef } from '../lib/palette.js';
import type { Theme } from '../lib/theme.js';

/** Command palette (Ctrl+P / /palette). Pure display: filtering
 *  and selection state live in App. Enter inserts the selected
 *  command into the composer (with a trailing space) so
 *  commands needing arguments can be completed there; it does
 *  not execute blindly. */
export function CommandPalette(props: {
	theme: Theme;
	query: string;
	commands: CommandDef[];
	selected: number;
}): React.ReactElement {
	const t = props.theme;
	return (
		<Box borderStyle="double" borderColor={t.primary} paddingX={1} flexDirection="column">
			<Text bold color={t.primary}>
				Command palette
			</Text>
			<Text>
				<Text color={t.muted}>/ </Text>
				<Text color={t.assistant}>{props.query}</Text>
				<Text color={t.primary}>▋</Text>
			</Text>
			{props.commands.length === 0 ? (
				<Text color={t.muted}>No matching command.</Text>
			) : (
				props.commands.slice(0, 10).map((cmd, i) => (
					<Text key={cmd.name}>
						<Text bold color={i === props.selected ? t.primary : t.muted}>
							{i === props.selected ? '› ' : '  '}
						</Text>
						<Text bold={i === props.selected} color={i === props.selected ? t.assistant : t.muted}>
							/{cmd.name}
						</Text>
						<Text color={t.muted}> — {cmd.description}</Text>
					</Text>
				))
			)}
			<Text color={t.muted}>↑↓ select · Enter insert into composer · Esc close</Text>
		</Box>
	);
}
