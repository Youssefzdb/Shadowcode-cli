# Shadowcode — next cycle (cycle 26, after cycle 25)

Cycle 24 is done except the items in MORNING_APPROVALS.md.

1. Live-provider smoke tests (morning approval, see
   MORNING_APPROVALS.md): one Groq free key + one live Ollama
   server/model, recorded in TESTING.md. Do not invent keys.
2. Free AI agents from other CLIs / websites — Kilo DONE in
   the user-authorised Kilo provider cycle (2026-11-02, version
   0.24.0): provider `kilo`, no key for free models, live-tested
   (see TESTING.md Kilo section). OpenCode Zen / other free
   agents remain a future choice by the user, not yet added.
   VPN / IP rotation to evade a rate limit was explicitly
   DECLINED and must not be added (see MORNING_APPROVALS.md
   section 27).
3. Go toolchain install (morning approval), then `make build-go`
   and a live test of the Go preview server + /search against the
   Python preview shapes (same /state.json, /shot.png), and a
   live Go-vs-Python search comparison on a real tree.
4. Interactive TUI on a real TTY: TS Ink TUI and Python curses TUI
   were tested for fallback/state only; a hand-driven session on
   a real terminal is still untested.
5. MCP: more servers / HTTP-local option only if the user
   explicitly approves it; keep remote servers out by default.
6. Context management: model-based summarisation for /compact
   (currently extractive only, by design).
7. Browser: multi-step form flows; selector coverage for more page
   structures; Go preview takeover wiring (POST /control equivalent).
   Cycle 19 is DONE for this item: tenth-site live replay
   (php.net, preview scroll_to on an archive 2026-10-21-4
   selector, then preview click_selector on the same selector,
   then on the archive page preview scroll_to on a ChangeLog
   8.5.12 selector and preview click_selector on it, then on
   the ChangeLog page preview scroll_to on a /sites.php
   selector and preview click_selector on it, then on the
   sites page preview scroll_to on a /contact.php selector
   and preview click_selector on it, not text, not a
   coordinate, not a goto) and scroll -> click x4 entries
   marked [scroll] [step 1] + [click-driven] [step 2] +
   [scroll] [step 3] + [click-driven] [step 4] + [scroll]
   [step 5] + [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: php.net home/archive news
   links carry absolute href attributes while footer links
   carry relative ones; the chain's selectors use each
   page's actual attribute form, verified by probe (the
   first guessed relative archive/ChangeLog selectors
   returned count=0 and were corrected, not claimed).
   Cycle 20 is DONE for this item: eleventh-site live replay
   (perl.org, preview scroll_to on a /contribute.html
   selector, then preview click_selector on the same selector,
   then on the contribute page preview scroll_to on a
   /siteinfo.html selector and preview click_selector on it,
   then on the siteinfo page preview scroll_to on a
   /about/whitepapers/ selector and preview click_selector
   on it, then on the whitepapers page preview scroll_to on
   an /app.html selector and preview click_selector on it,
   then on the app page preview scroll_to on a
   /about/style-guide.html selector and preview
   click_selector on it, not text, not a coordinate, not a
   goto) and scroll -> click x5 entries marked [scroll]
   [step 1] + [click-driven] [step 2] + [scroll] [step 3] +
   [click-driven] [step 4] + [scroll] [step 5] +
   [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] + [scroll] [step 9] +
   [click-driven] [step 10] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: perl.org chain selectors
   verified by probe (contribute top 700, siteinfo top 930,
   whitepapers top 2044, app top 903, style-guide top 1208);
   whitepapers and app pages each timed out once in probes
   then loaded on retry, /camel.html timed out and was NOT
   used, and the live chain landed every page first try.
   Script-note honesty: the live script ran from the home
   directory, so its saved log first landed in
   ~/test-workspace/.shadowcode/; it was moved unchanged
   into test-workspace/.shadowcode/ and the stray directory
   removed (see TESTING.md cycle 20).
   Cycle 21 is DONE for this item: twelfth-site live replay
   (scala-lang.org, preview scroll_to on a /conduct.html
   selector, then preview click_selector on the same selector,
   then on the conduct page preview scroll_to on a /license/
   selector and preview click_selector on it, then on the
   license page preview scroll_to on a /security/ selector
   and preview click_selector on it, then on the security
   page preview scroll_to on a /governance/ selector and
   preview click_selector on it, then on the governance page
   preview scroll_to on a /blog/ selector and preview
   click_selector on it, then on the blog page preview
   scroll_to on a /download/ selector and preview
   click_selector on it, not text, not a coordinate, not a
   goto) and scroll -> click x6 entries marked [scroll]
   [step 1] + [click-driven] [step 2] + [scroll] [step 3] +
   [click-driven] [step 4] + [scroll] [step 5] +
   [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] + [scroll] [step 9] +
   [click-driven] [step 10] + [scroll] [step 11] +
   [click-driven] [step 12] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: scala-lang.org chain
   selectors verified by probe (conduct top 2537 on home,
   license top 4408 on conduct, security top 887 on
   license; governance/blog/download selectors match the
   nav first, top 39, on their source pages); the conduct
   click canonicalised from /conduct.html to /conduct/,
   recorded as a non-action title-settle entry in the saved
   log with no step number. The live script was run from
   inside ~/workspace/shadowcode, so its saved log landed
   directly in test-workspace/.shadowcode/ with no move.
   Cycle 22 is DONE for this item: thirteenth-site live replay
   (elixir-lang.org, preview scroll_to on a /install/ selector,
   then preview click_selector on the same selector, then on
   the install page preview scroll_to on a /learning/ selector
   and preview click_selector on it, then on the learning page
   preview scroll_to on a /docs/ selector and preview
   click_selector on it, then on the docs page preview
   scroll_to on a /cases/ selector and preview click_selector
   on it, then on the cases page preview scroll_to on a /blog/
   selector and preview click_selector on it, then on the blog
   page preview scroll_to on a /development/ selector and
   preview click_selector on it, then on the development page
   preview scroll_to on a /trademarks/ selector and preview
   click_selector on it, not text, not a coordinate, not a
   goto) and scroll -> click x7 entries marked [scroll]
   [step 1] + [click-driven] [step 2] + [scroll] [step 3] +
   [click-driven] [step 4] + [scroll] [step 5] +
   [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] + [scroll] [step 9] +
   [click-driven] [step 10] + [scroll] [step 11] +
   [click-driven] [step 12] + [scroll] [step 13] +
   [click-driven] [step 14] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: elixir-lang.org chain
   selectors verified by probe (install nav first match top
   78 on home; learning/docs/cases/blog nav first matches
   top 78 on their source pages; development footer link on
   the blog page; trademarks top 3191 on the development
   page); the blog page carries NO /stewards/ link, so
   blog -> development -> trademarks replaced the
   first-planned blog -> stewards pair before the live run.
   The live script was run from inside ~/workspace/shadowcode,
   so its saved log landed directly in
   test-workspace/.shadowcode/ with no move.
   Cycle 23 is DONE for this item: fourteenth-site live replay
   (lua.org, preview scroll_to on a start.html selector,
   then preview click_selector on the same selector, then on
   the start page preview scroll_to on a docs.html selector
   and preview click_selector on it, then on the docs page
   preview scroll_to on a faq.html selector and preview
   click_selector on it, then on the faq page preview
   scroll_to on a versions.html selector and preview
   click_selector on it, then on the versions page preview
   scroll_to on a license.html selector and preview
   click_selector on it, then on the license page preview
   scroll_to on a authors.html selector and preview
   click_selector on it, then on the authors page preview
   scroll_to on a thanks.html selector and preview
   click_selector on it, then on the thanks page preview
   scroll_to on a donations.html selector and preview
   click_selector on it, not text, not a coordinate, not a
   goto) and scroll -> click x8 entries marked [scroll]
   [step 1] + [click-driven] [step 2] + [scroll] [step 3] +
   [click-driven] [step 4] + [scroll] [step 5] +
   [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] + [scroll] [step 9] +
   [click-driven] [step 10] + [scroll] [step 11] +
   [click-driven] [step 12] + [scroll] [step 13] +
   [click-driven] [step 14] + [scroll] [step 15] +
   [click-driven] [step 16] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: lua.org chain selectors
   verified by probe (start.html count 1, top 174 on home;
   docs.html count 1, top 726 on start; faq.html count 2,
   first top 202 on docs; versions.html count 2, first top
   1326 on faq; license.html count 1, top 1545 on versions;
   authors.html count 1, top 530 on license; thanks.html
   count 1, top 552 on authors; donations.html count 1 on
   thanks); the thanks page carries NO contact.html link,
   so thanks -> donations replaced the first-planned
   thanks -> contact pair before the live run. The live
   script was run from inside ~/workspace/shadowcode,
   so its saved log landed directly in
   test-workspace/.shadowcode/ with no move.
   Cycle 24 is DONE for this item: fifteenth-site live replay
   (ocaml.org, preview scroll_to on a /docs selector, then
   preview click_selector on the same selector, then on the
   docs page preview scroll_to on a /tools selector and
   preview click_selector on it (landing /platform), then on
   the platform page preview scroll_to on a /packages
   selector and preview click_selector on it, then on the
   packages page preview scroll_to on a /community selector
   and preview click_selector on it, then on the community
   page preview scroll_to on a /changelog selector and
   preview click_selector on it, then on the changelog page
   preview scroll_to on a /events selector and preview
   click_selector on it, then on the events page preview
   scroll_to on a /jobs selector and preview click_selector
   on it, then on the jobs page preview scroll_to on a
   /security selector and preview click_selector on it,
   then on the security page preview scroll_to on a
   /governance selector and preview click_selector on it,
   not text, not a coordinate, not a goto) and scroll ->
   click x9 entries marked [scroll] [step 1] +
   [click-driven] [step 2] + [scroll] [step 3] +
   [click-driven] [step 4] + [scroll] [step 5] +
   [click-driven] [step 6] + [scroll] [step 7] +
   [click-driven] [step 8] + [scroll] [step 9] +
   [click-driven] [step 10] + [scroll] [step 11] +
   [click-driven] [step 12] + [scroll] [step 13] +
   [click-driven] [step 14] + [scroll] [step 15] +
   [click-driven] [step 16] + [scroll] [step 17] +
   [click-driven] [step 18] with a steps footer in both TUIs'
   /browser-watch-replay, with both driver transitions.
   Probe note, honestly recorded: ocaml.org chain selectors
   verified by probe (docs count 2, nav first top 16 on home;
   tools count 2, nav first top 16 on docs; packages count 3,
   nav first top 16 on platform; community count 3, nav first
   top 16 on packages; changelog count 3, nav first top 16 on
   community; events count 1, top 49853 on changelog; jobs
   count 2, first top 80 on events; security count 1,
   top 3020 on jobs; governance count 1, top 2604 on
   security); the /play page carries NO /events link, so
   changelog -> events replaced the first-planned
   changelog -> play -> events route before the live run,
   and /tools canonicalises to /platform, so the first live
   run was aborted on its landing check (partial 7-entry log,
   NOT claimed) and the corrected chain landed every page
   first try. The live script was run from inside
   ~/workspace/shadowcode, so its saved log landed directly
   in test-workspace/.shadowcode/ with no move.
   Next browser item: a seventeenth site with an eleven-page
   chain — scroll -> click x11 (steps 1..22) — or, if no clean
   eleven-page chain loads, a multi-step form flow on a public
   documentation site, to prove the sequence composes further.
8. Packaging: verify `pip install -e .` puts `shadowcode` on PATH
   (install step deferred to the morning; offline verification
   via tests/verify_packaging.py is done).
9. Benchmark follow-up: repeat scripts/benchmark_search.py on a
   larger tree and with a regex query (Python-only path), and
   record whether the native win holds when the cap is raised.
10. Cycle 10 follow-up: health-history rotation beyond the 100-cap
    (e.g. monthly archive) only if the user wants it; the cap
    itself is already in place, so no unbounded growth today.
