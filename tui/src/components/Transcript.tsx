import React from 'react';
import { Box, Text } from 'ink';
import { toolStatusMark, truncate, type TranscriptLine } from '../lib/protocol.js';
import { parseMarkdownSegments } from '../lib/markdown.js';
import type { Theme } from '../lib/theme.js';

export function Transcript(props: { lines: TranscriptLine[]; theme: Theme }): React.ReactElement {
	const t = props.theme;
	return (
		<Box flexDirection="column" flexGrow={1}>
			{props.lines.map((line, i) => {
				if (line.kind === 'user') {
					return (
						<Text key={i}>
							<Text bold color={t.user}>
								›{' '}
							</Text>
							<Text color={t.user}>{line.text}</Text>
						</Text>
					);
				}
				if (line.kind === 'assistant') {
					return (
						<Text key={i} color={t.assistant}>
							{parseMarkdownSegments(line.text).map((seg, j) => (
								<Text key={j} bold={seg.bold} color={seg.code ? t.secondary : undefined}>
									{seg.text}
								</Text>
							))}
						</Text>
					);
				}
				if (line.kind === 'tool') {
					const failed = toolStatusMark(line.result) === '✕';
					return (
						<Text key={i}>
							<Text bold color={failed ? t.error : t.success}>
								{failed ? '✕' : '✓'} {line.name}{' '}
							</Text>
							<Text color={t.muted}>{truncate(line.result.replace(/\n/g, ' '), 200)}</Text>
						</Text>
					);
				}
				return (
					<Text key={i} color={t.system}>
						{line.text}
					</Text>
				);
			})}
		</Box>
	);
}
