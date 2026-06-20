# Word Count Contract Fix Design

## Problem

`split_chapters()` defines `word_count` as the number of non-whitespace
characters, including punctuation. The ingestion-level total uses the same
rule. An older unit test removes newlines but retains spaces, so it expects a
different result and fails on otherwise consistent behavior.

## Decision

Keep the production behavior unchanged: chapter and novel `word_count` values
exclude every whitespace character recognized by Python's `\s` pattern. Update
the test expectation and comment to express that contract directly.

## Scope

- Change only the incorrect test expectation and its explanatory comment.
- Do not change ingestion output or migrate stored material.
- Verify the focused regression test, then the complete test suite.

## Success Criteria

- The word-count test expects the title space and newline to be excluded.
- The focused test passes.
- The complete test suite passes before the feature branch is merged.
