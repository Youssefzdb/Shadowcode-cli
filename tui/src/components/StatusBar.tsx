import React from 'react';
import { Box, Text } from 'ink';
import { autoAcceptLabel, type PermissionMode } from '../lib/mode.js';
import type { Theme } from '../lib/theme.js';

/** Claude-style bottom status bar (Design 1):
 * left — `ESC to interrupt • ↑/↓ history • /help commands`;
 * right — real permission state, cwd, and git branch ONLY
 * when the workdir really is a git repo (gitBranch === null
 * omits the field). Lines-changed is deliberately absent:
 * tool results carry no line-change count, so any number
 * here would be invented. Tokens/cost are likewise absent:
 * the protocol does not report them.
 */
export function StatusBar(props: {
	theme: Theme;
	thinking: boolean;
	spinner: string;
	permissionMode: PermissionMode;
	allowDestructive: boolean;
	cwd: string;
	gitBranch: string | null;
}): React.ReactElement {
	const t = props.theme;
	return (
		<Box flexDirection="row" justifyContent="space-between" paddingX={1}>
			<Text color={t.muted}>
				{props.thinking ? `${props.spinner} ` : ''}ESC to interrupt • ↑/↓ history • /help commands
			</Text>
			<Text color={t.muted}>
				{autoAcceptLabel(props.permissionMode, props.allowDestructive)} • cwd: {props.cwd}
				{props.gitBranch ? ` • git: ${props.gitBranch}` : ''}
			</Text>
		</Box>
	);
}
