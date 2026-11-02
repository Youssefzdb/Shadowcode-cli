import React from 'react';
import { Box, Text } from 'ink';
import { toolStatusMark, truncate, type TranscriptLine } from '../lib/protocol.js';

export function Transcript(props: { lines: TranscriptLine[] }): React.ReactElement {
	return (
		<Box flexDirection="column" flexGrow={1}>
			{props.lines.map((line, i) => {
				if (line.kind === 'user') {
					return (
						<Text key={i} color="green">
							&gt; {line.text}
						</Text>
					);
				}
				if (line.kind === 'assistant') {
					return <Text key={i}>{line.text}</Text>;
				}
				if (line.kind === 'tool') {
					return (
						<Text key={i} color="yellow">
							[tool {line.name}] {toolStatusMark(line.result)} {truncate(line.result.replace(/\n/g, ' '), 200)}
						</Text>
					);
				}
				return (
					<Text key={i} color="gray">
						{line.text}
					</Text>
				);
			})}
		</Box>
	);
}
