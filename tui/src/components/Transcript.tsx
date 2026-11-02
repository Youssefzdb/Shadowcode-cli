import React from 'react';
import { Box, Text } from 'ink';
import { truncate, type TranscriptLine } from '../lib/protocol.js';
import { toolCardBorderColor, toolDisplayName, toolLineStatus } from '../lib/toolCards.js';
import { parseMarkdownSegments } from '../lib/markdown.js';
import type { Theme } from '../lib/theme.js';

/** Claude-style transcript (Design 1): user lines are
 * `> user` + an indented `> text` line, assistant lines are
 * `• shadowcode` + the reply (bold/`code` segments kept),
 * and every tool result is a bordered card — green when done,
 * red when failed — with `✓/✕ Title` and a muted preview
 * underneath. Cards come only from real protocol tool lines.
 */
export function Transcript(props: { lines: TranscriptLine[]; theme: Theme }): React.ReactElement {
	const t = props.theme;
	return (
		<Box flexDirection="column" flexGrow={1}>
			{props.lines.map((line, i) => {
				if (line.kind === 'user') {
					return (
						<Box key={i} flexDirection="column">
							<Text bold color={t.user}>
								&gt; user
							</Text>
							<Text color={t.assistant}>  &gt; {line.text}</Text>
						</Box>
					);
				}
				if (line.kind === 'assistant') {
					return (
						<Box key={i} flexDirection="column">
							<Text bold color={t.assistant}>
								• shadowcode
							</Text>
							<Text color={t.assistant}>
								{parseMarkdownSegments(line.text).map((seg, j) => (
									<Text key={j} bold={seg.bold} color={seg.code ? t.secondary : undefined}>
										{seg.text}
									</Text>
								))}
							</Text>
						</Box>
					);
				}
				if (line.kind === 'tool') {
					const status = toolLineStatus(line.result);
					const border = toolCardBorderColor(status, t);
					const mark = status === 'failed' ? '✕' : '✓';
					return (
						<Box key={i} borderStyle="single" borderColor={border} paddingX={1} flexDirection="column">
							<Text bold color={border}>
								{mark} {toolDisplayName(line.name, line.result)}
							</Text>
							<Text color={t.muted}>{truncate(line.result.replace(/\n/g, ' '), 200)}</Text>
						</Box>
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
