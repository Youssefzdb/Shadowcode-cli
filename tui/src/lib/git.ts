/** Git branch detection for the status bar — honest, local only.
 *
 * Reads `.git/HEAD` in the workdir (following a `gitdir:` pointer
 * for worktrees). Returns the branch name, or null when the
 * workdir is not a git repo, HEAD is unreadable, or HEAD is
 * detached (a detached HEAD has no branch name to show, so the
 * status bar omits the git field entirely rather than showing
 * a misleading branch). No `git` subprocess is spawned, and no
 * dirty/clean marker is claimed: that would need `git status`,
 * which this helper deliberately does not run.
 */
import { readFileSync, statSync } from 'node:fs';
import path from 'node:path';

/** Parse the raw contents of a .git/HEAD file. */
export function parseGitHead(headContent: string): string | null {
	const line = headContent.trim();
	const m = /^ref:\s*refs\/heads\/(.+)$/.exec(line);
	if (m) return (m[1] ?? '').trim() || null;
	// Detached HEAD (a bare SHA) or garbage: no branch name.
	return null;
}

/** Branch name for a workdir, or null when not a git repo. */
export function readGitBranch(workdir: string): string | null {
	try {
		const dotGit = path.join(workdir, '.git');
		const st = statSync(dotGit);
		let gitDir = dotGit;
		if (st.isFile()) {
			// Worktree pointer file: "gitdir: <path>"
			const m = /^gitdir:\s*(.+)$/m.exec(readFileSync(dotGit, 'utf8').trim());
			if (!m) return null;
			const target = (m[1] ?? '').trim();
			gitDir = path.isAbsolute(target) ? target : path.resolve(workdir, target);
		} else if (!st.isDirectory()) {
			return null;
		}
		return parseGitHead(readFileSync(path.join(gitDir, 'HEAD'), 'utf8'));
	} catch {
		return null;
	}
}
