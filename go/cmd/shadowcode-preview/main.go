// Command shadowcode-preview is the Go localhost service for
// Shadowcode: a live browser-preview server and a fast file-search
// service. It binds to 127.0.0.1 only, never to a public interface.
//
// Endpoints (see go/README.md):
//   GET  /health                  {"ok": true}
//   GET  /state.json              current preview state (title/url/driver)
//   GET  /shot.png                latest screenshot (posted by the browser owner)
//   POST /shot  (body: PNG bytes) replace the screenshot
//   POST /state (JSON)            replace title/url/driver
//   POST /takeover /handback      set driver=user|agent
//   GET  /search?q=...            file search in the workdir (JSON hits)
//   GET  /                        the web preview frontend (../web/)
//
// The Python browser thread remains the browser owner in the
// current Python-core flow; this Go server is the high-concurrency
// replacement for the preview HTTP layer, and it accepts the same
// /state.json and /shot.png shapes, so the TS TUI and the Python
// preview page keep working either way.
//
// Build (needs a Go toolchain — see MORNING_APPROVALS.md if the
// toolchain is not installed in this environment):
//   go build -o shadowcode-preview ./cmd/shadowcode-preview
// Run:
//   ./shadowcode-preview --workdir ../test-workspace --port 8765
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	"shadowcode/preview/internal/search"
)

type State struct {
	Title  string `json:"title"`
	URL    string `json:"url"`
	Driver string `json:"driver"`
}

type Server struct {
	mu     sync.RWMutex
	state  State
	shot   []byte
	workdir string
	webdir  string
}

func (s *Server) json(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	s.json(w, map[string]bool{"ok": true})
}

func (s *Server) handleState(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		var st State
		if err := json.NewDecoder(r.Body).Decode(&st); err != nil {
			http.Error(w, "bad json", http.StatusBadRequest)
			return
		}
		s.mu.Lock()
		s.state = st
		s.mu.Unlock()
		s.json(w, map[string]bool{"ok": true})
		return
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	s.json(w, map[string]any{
		"title": s.state.Title, "url": s.state.URL, "driver": s.state.Driver,
		"has_screenshot": len(s.shot) > 0,
	})
}

func (s *Server) handleShot(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		body, err := io.ReadAll(io.LimitReader(r.Body, 10<<20))
		if err != nil {
			http.Error(w, "read failed", http.StatusBadRequest)
			return
		}
		s.mu.Lock()
		s.shot = body
		s.mu.Unlock()
		s.json(w, map[string]bool{"ok": true})
		return
	}
	s.mu.RLock()
	shot := s.shot
	s.mu.RUnlock()
	if len(shot) == 0 {
		http.Error(w, "no screenshot yet", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "image/png")
	_, _ = w.Write(shot)
}

func (s *Server) handleDriver(driver string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		s.mu.Lock()
		s.state.Driver = driver
		s.mu.Unlock()
		s.json(w, map[string]bool{"ok": true})
	}
}

func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "q required", http.StatusBadRequest)
		return
	}
	hits, err := search.Search(s.workdir, q, 100)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	s.json(w, hits)
}

func main() {
	workdir := flag.String("workdir", ".", "workdir for /search (confined there)")
	port := flag.Int("port", 8765, "localhost port")
	flag.Parse()
	wd, err := filepath.Abs(*workdir)
	if err != nil {
		log.Fatal(err)
	}
	srv := &Server{workdir: wd, webdir: filepath.Join(filepath.Dir(os.Args[0]), "..", "web")}
	// Serve the web frontend from the repo web/ dir when present.
	webdir := "web"
	if _, err := os.Stat(webdir); err == nil {
		srv.webdir = webdir
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.handleHealth)
	mux.HandleFunc("/state.json", srv.handleState)
	mux.HandleFunc("/shot.png", srv.handleShot)
	mux.HandleFunc("/shot", srv.handleShot)
	mux.HandleFunc("/state", srv.handleState)
	mux.HandleFunc("/takeover", srv.handleDriver("user"))
	mux.HandleFunc("/handback", srv.handleDriver("agent"))
	mux.HandleFunc("/search", srv.handleSearch)
	mux.Handle("/", http.FileServer(http.Dir(srv.webdir)))
	addr := fmt.Sprintf("127.0.0.1:%d", *port)
	log.Printf("shadowcode-preview on http://localhost:%d (workdir=%s)", *port, wd)
	log.Fatal(http.ListenAndServe(addr, mux))
}
