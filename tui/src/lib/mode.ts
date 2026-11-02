/** Mode mapping for the Shadowcode Ink TUI.
 *
 * The Python core only knows three permission modes (see
 * shadowcode_pkg/permissions.py). The TUI displays them with
 * modern labels — Plan / Build / Ask — but the string passed
 * to the core via --permission-mode is ALWAYS the real core
 * mode. No new permission is invented here.
 *
 *   plan   -> Plan  : read-only, write/shell tools refused
 *   auto   -> Build : read tools auto; writes/shell guarded
 *                     (in subprocess mode: denied unless
 *                     --allow-destructive + --yes was given)
 *   manual -> Ask   : write/shell tools need confirmation
 *
 * Aliases 'build' and 'ask' are accepted at the prompt and
 * normalised to the core mode before anything is sent.
 */

export type PermissionMode = 'manual' | 'auto' | 'plan';

export interface ModeInfo {
	mode: PermissionMode;
	label: string;
	description: string;
}

export const MODE_INFO: Record<PermissionMode, ModeInfo> = {
	plan: {
		mode: 'plan',
		label: 'Plan',
		description: 'Read-only: write/shell tools are refused by the core.',
	},
	auto: {
		mode: 'auto',
		label: 'Build',
		description: 'Auto: read tools run freely; writes/shell stay guarded.',
	},
	manual: {
		mode: 'manual',
		label: 'Ask',
		description: 'Ask: write/shell tools need confirmation before running.',
	},
};

/** Parse user input into a real core permission mode, or null. */
export function parseMode(input: string): PermissionMode | null {
	const v = input.trim().toLowerCase();
	if (v === 'plan') return 'plan';
	if (v === 'auto' || v === 'build') return 'auto';
	if (v === 'manual' || v === 'ask') return 'manual';
	return null;
}

export function modeInfo(mode: PermissionMode): ModeInfo {
	return MODE_INFO[mode];
}

export function modeLabel(mode: PermissionMode): string {
	return MODE_INFO[mode].label;
}
