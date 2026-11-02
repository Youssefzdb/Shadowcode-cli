import React from 'react';
import { Box, Text } from 'ink';
import type { Theme } from '../lib/theme.js';

/** Health-history panel: the last /health-history output, shown as
 * its own panel (not only buried in the transcript) so the user
 * can read the newest-first snapshots at a glance. Rendered only
 * after /health-history; hidden again with /health-history-hide.
 * Lines are the core's output verbatim — nothing is invented. */
export function HealthHistoryPanel(props: { lines: string[]; theme?: Theme }): React.ReactElement {
	const t = props.theme;
	return (
		<Box borderStyle="single" borderColor={t?.border ?? 'green'} paddingX={1} flexDirection="column">
			<Text bold color={t?.success ?? 'green'}>
				Health history
			</Text>
			{props.lines.map((l, i) => (
				<Text key={i}>{l}</Text>
			))}
		</Box>
	);
}
