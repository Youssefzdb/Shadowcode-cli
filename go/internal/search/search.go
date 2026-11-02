// Package search is a fast, stdlib-only file search/index service
// used by the Go preview/search server. It walks a workdir, skips
// VCS and dependency directories, and returns ranked line hits.
// No external dependencies, so it builds with `go build` alone.
package search

import (
	"bufio"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Hit struct {
	Path    string `json:"path"`
	Line    int    `json:"line"`
	Text    string `json:"text"`
	Matches int    `json:"matches"`
}

var skipDirs = map[string]bool{
	".git": true, "node_modules": true, "__pycache__": true, "dist": true, ".venv": true,
}

// Search walks root and returns hits for query (case-insensitive
// substring, per line), newest files first by path order, capped.
func Search(root, query string, cap int) ([]Hit, error) {
	if cap <= 0 {
		cap = 100
	}
	q := strings.ToLower(query)
	var hits []Hit
	err := filepath.Walk(root, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // unreadable file/dir: skip, do not fail the search
		}
		if info.IsDir() {
			if skipDirs[info.Name()] && p != root {
				return filepath.SkipDir
			}
			return nil
		}
		if info.Size() > 1<<20 { // skip >1MiB files (binaries, bundles)
			return nil
		}
		f, err := os.Open(p)
		if err != nil {
			return nil
		}
		defer f.Close()
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 64*1024), 1024*1024)
		lineno := 0
		for sc.Scan() {
			lineno++
			line := sc.Text()
			n := strings.Count(strings.ToLower(line), q)
			if n > 0 {
				rel, _ := filepath.Rel(root, p)
				text := strings.TrimSpace(line)
				if len(text) > 200 {
					text = text[:200]
				}
				hits = append(hits, Hit{Path: rel, Line: lineno, Text: text, Matches: n})
				if len(hits) >= cap {
					return filepath.SkipAll
				}
			}
		}
		return nil
	})
	if err != nil {
		return hits, err
	}
	// Rank: more matches first, then path, then line — deterministic.
	sort.SliceStable(hits, func(i, j int) bool {
		if hits[i].Matches != hits[j].Matches {
			return hits[i].Matches > hits[j].Matches
		}
		if hits[i].Path != hits[j].Path {
			return hits[i].Path < hits[j].Path
		}
		return hits[i].Line < hits[j].Line
	})
	return hits, nil
}
