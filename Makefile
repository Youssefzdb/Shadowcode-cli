# Shadowcode — polyglot monorepo build orchestration
# Languages: Python (agent core), TypeScript (TUI + web frontend),
# Go (preview/search service), C++ (native scanner). See docs/ARCHITECTURE.md.
# No step here installs anything outside the project or touches an
# external account. Go build is skipped gracefully if no Go toolchain
# is present (see MORNING_APPROVALS.md).

.PHONY: build-all build-tui build-go build-native test-all test-python test-tui test-native clean

build-all: build-tui build-native
	@echo "build-all done (Go skipped if no toolchain; run 'make build-go' after installing Go)"

build-tui:
	cd tui && npm run build

build-go:
	cd go && go build -o shadowcode-preview ./cmd/shadowcode-preview

build-native:
	cd native && make

test-all: test-python test-tui test-native

test-python:
	python3 tests/run_tests.py

test-tui:
	cd tui && npm test

test-native:
	cd native && make test

clean:
	rm -rf tui/dist native/shadowcode-native native/libshadowcode_native.so
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
