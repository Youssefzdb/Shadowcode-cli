import React from 'react';
import { Box, Text } from 'ink';
import { toolStatusMark, truncate, type TranscriptLine } from '../lib/protocol.js';

/** ToolPanel: the most recent tool calls, newest first, capped. */
export function ToolPanel(props: { lines: TranscriptLine[] }): React.ReactElement {
	const tools = props.lines.filter((l) => l.kind === 'tool').slice(-5).reverse();
	if (tools.length === 0) return <Box />;
	return (
		<Box borderStyle="single" borderColor="yellow" paddingX={1} flexDirection="column">
			<Text bold color="yellow">
				Tools
			</Text>
			{tools.map((t, i) =>
				t.kind === 'tool' ? (
					<Text key={i}>
						{t.name} {toolStatusMark(t.result)} {truncate(t.result.replace(/\n/g, ' '), 120)}
					</Text>
				) : null,
			)}
		</Box>
	);
}
