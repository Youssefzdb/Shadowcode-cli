#!/bin/sh
# Native tests: no framework, plain assertions on real output.
set -e
cd "$(dirname "$0")/.."
./shadowcode-native count ../test-workspace/hello.txt | grep -q "lines="
SCORE=$(./shadowcode-native fuzzy scd shadowcode | sed 's/score=//')
[ "$SCORE" -gt 0 ] || { echo "fuzzy should match"; exit 1; }
./shadowcode-native fuzzy xyz shadowcode | grep -q "score=0"
./shadowcode-native search ../test-workspace shadowcode 100 | grep -q "hello.txt"
echo "native tests passed"
