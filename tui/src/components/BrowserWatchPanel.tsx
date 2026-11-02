import React from 'react';
import { Box, Text } from 'ink';
import { countClickDriven, countScroll, countTransitions, formatReplayEntries, type ReplayEntry } from '../lib/replay.js';

/** Browser watch panel: the FULL replay on demand, not the tail.
 * Rendered only when the user runs /browser-watch-replay; hidden
 * again with /browser-watch-hide. Entries come from the saved
 * workspace watch log (see lib/replay.ts), never from the live
 * preview's 10-entry tail. Cycle 11 polish: the header now shows
 * the transition count, so a no-navigation takeover/handback
 * (same page, 2 transitions) is visible at a glance instead of
 * looking like an empty replay. */
export function BrowserWatchPanel(props: { entries: ReplayEntry[]; savedFile: string | null }): React.ReactElement {
	const lines = formatReplayEntries(props.entries, props.savedFile ?? '');
	const transitions = countTransitions(props.entries);
	const clicks = countClickDriven(props.entries);
	const scrolls = countScroll(props.entries);
	return (
		<Box borderStyle="single" borderColor="cyan" paddingX={1} flexDirection="column">
			<Text bold color="cyan">
				Browser watch replay (full) — {props.entries.length} entries, {transitions} driver transition{transitions === 1 ? '' : 's'}
				{clicks > 0 ? `, ${clicks} click-driven` : ''}
				{scrolls > 0 ? `, ${scrolls} scroll` : ''}
				{scrolls + clicks > 0 ? `, ${scrolls + clicks} action step${scrolls + clicks === 1 ? '' : 's'}` : ''}
			</Text>
			{lines.map((l, i) => (
				<Text key={i}>{l}</Text>
			))}
		</Box>
	);
}
