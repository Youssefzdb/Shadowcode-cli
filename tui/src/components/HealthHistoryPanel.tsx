import React from 'react';
import { Box, Text } from 'ink';

/** Health-history panel: the last /health-history output, shown as
 * its own panel (not only buried in the transcript) so the user
 * can read the newest-first snapshots at a glance. Rendered only
 * after /health-history; hidden again with /health-history-hide.
 * Lines are the core's output verbatim — nothing is invented. */
export function HealthHistoryPanel(props: { lines: string[] }): React.ReactElement {
	return (
		<Box borderStyle="single" borderColor="green" paddingX={1} flexDirection="column">
			<Text bold color="green">
				Health history
			</Text>
			{props.lines.map((l, i) => (
				<Text key={i}>{l}</Text>
			))}
		</Box>
	);
}
