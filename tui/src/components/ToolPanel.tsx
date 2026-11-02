import React from 'react';
import { Box, Text } from 'ink';
import { cardPreview, formatElapsed, toolCardBorderColor, toolDisplayName, type ToolCard } from '../lib/toolCards.js';
import type { Theme } from '../lib/theme.js';

/** Live tool panel (right sidebar, collapsible via Ctrl+T / /panel).
 *
 * Cards come from REAL `tool` protocol events (see lib/toolCards
 * for the honest limit: the core emits a tool event only after
 * execution, so a named card is done/failed on arrival; the
 * "working…" row below is the generic live-running indicator
 * while a turn is in flight, never a faked named tool).
 */
export function ToolPanel(props: {
	theme: Theme;
	cards: ToolCard[];
	thinking: boolean;
	spinner: string;
	collapsed: boolean;
}): React.ReactElement {
	const t = props.theme;
	if (props.collapsed) {
		return (
			<Box borderStyle="single" borderColor={t.border} paddingX={1}>
				<Text color={t.muted}>Tools ▸ (Ctrl+T)</Text>
			</Box>
		);
	}
	const shown = [...props.cards].reverse().slice(0, 8);
	const running = props.cards.filter((c) => c.status === 'running').length;
	return (
		<Box borderStyle="single" borderColor={t.border} paddingX={1} flexDirection="column" width={38}>
			<Text bold color={t.tool}>
				Tools {props.cards.length > 0 ? `(${props.cards.length})` : ''} {running > 0 ? `· ${running} running` : ''}
			</Text>
			{props.thinking ? (
				<Text color={t.primary}>
					{props.spinner} working…
				</Text>
			) : null}
			{shown.length === 0 && !props.thinking ? <Text color={t.muted}>No tools yet.</Text> : null}
			{shown.map((card) => {
				const icon = card.status === 'running' ? '◐' : card.status === 'done' ? '✓' : '✕';
				const color = toolCardBorderColor(card.status, t);
				return (
					<Box key={card.id} flexDirection="column">
						<Text>
							<Text bold color={color}>
								{icon} {toolDisplayName(card.name, card.result)}
							</Text>
							<Text color={t.muted}>{card.elapsedMs !== undefined ? ` ${formatElapsed(card.elapsedMs)}` : ''}</Text>
						</Text>
						{card.result ? (
							<Text color={t.muted}>  {cardPreview(card)}</Text>
						) : null}
					</Box>
				);
			})}
		</Box>
	);
}
