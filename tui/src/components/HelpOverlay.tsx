import React from 'react';
import { Box, Text } from 'ink';
import { COMMANDS } from '../lib/palette.js';
import type { Theme } from '../lib/theme.js';

/** Help overlay (/help). Pure display — key handling
 *  lives in App so Esc cannot double-fire. This replaces
 *  the old wall of /help text dumped into the transcript. */
export function HelpOverlay(props: { theme: Theme }): React.ReactElement {
	const t = props.theme;
	return (
		<Box borderStyle="double" borderColor={t.primary} paddingX={1} flexDirection="column">
			<Text bold color={t.primary}>
				Shadowcode — help
			</Text>
			<Text color={t.muted}>Keys: Ctrl+P palette · Esc close · Ctrl+T tools panel · Up/Down history · Ctrl+C quit</Text>
			<Text color={t.muted}>Type a prompt to talk to the agent. Slash commands are handled locally.</Text>
			{COMMANDS.map((cmd) => (
				<Text key={cmd.name}>
					<Text bold color={t.assistant}>
						/{cmd.name}
					</Text>
					<Text color={t.muted}> — {cmd.description}</Text>
				</Text>
			))}
			<Text color={t.muted}>Permission note: in subprocess mode destructive tools are denied unless --allow-destructive was passed; no prompt is faked here.</Text>
		</Box>
	);
}
