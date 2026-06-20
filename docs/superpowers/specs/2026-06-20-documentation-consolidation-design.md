# Documentation Consolidation Design

## Goal

Reorganize the project documentation so that active documents describe the
current code and the agreed product direction, while obsolete reference and
completed implementation documents no longer compete with the active sources
of truth.

## Product Decisions That Documentation Must Preserve

- Novel Material is a writing-reference retrieval library, not an internal
  prose-generation system.
- The repository is responsible for retrieval and structured presentation;
  the external Agent is responsible for understanding, combining, and
  generating from references.
- Retrieval quality is the primary objective. A response time of up to three
  minutes is acceptable for deep, high-quality retrieval.
- Existing 4096-dimensional embeddings remain the quality baseline. Dimension
  reduction is not an assumed requirement and may only be considered after a
  measured quality comparison.
- The long-term capacity range is 500 to 5000 novels, approximately 250,000 to
  2.5 million chapters at 500 chapters per novel.
- Chapters remain the smallest analysis unit. Event and scene splitting remain
  explicitly out of scope.

## Documentation Sources of Truth

| Document | Responsibility |
|---|---|
| `README.md` | Project entry point, current capabilities, quick start, documentation map |
| `docs/REQUIREMENTS.md` | Product boundary, priorities, scale, quality targets, non-goals |
| `ARCHITECTURE.md` | Current implemented architecture, data flow, module boundaries, known constraints |
| `docs/USER_MANUAL.md` | Commands and operating procedures verified against the installed CLI |
| `AGENTS.md` | Generic/Codex agent operating rules |
| `CLAUDE.md` | Claude Code operating rules, synchronized with `AGENTS.md` except platform-specific paths |
| `docs/GENRE_AWARE_ANALYSIS.md` | Active guide for the implemented genre-aware insights feature |
| `docs/README.md` | Documentation index, status, authority, and reading order |

When documents conflict, the order is:

1. `docs/REQUIREMENTS.md` for product decisions.
2. `ARCHITECTURE.md` for implemented technical structure.
3. `docs/USER_MANUAL.md` for verified usage.
4. `AGENTS.md` or `CLAUDE.md` for agent behavior.
5. `README.md` as a concise summary of the documents above.

## File Disposition

### Create

- `docs/README.md`: index all retained documentation and label each document as
  active specification, active guide, backlog, archive, generated plan, or
  subsystem contract.

### Update

- `README.md`
  - Keep it concise and beginner-friendly.
  - Add genre-aware insights to the capability overview.
  - Correct paths and prerequisites.
  - Link to `docs/README.md` rather than duplicating detailed explanations.
- `docs/REQUIREMENTS.md`
  - Replace the universal two-second requirement with quality-first retrieval.
  - Record the accepted three-minute ceiling for deep retrieval.
  - Expand the planned corpus range to 500-5000 novels.
  - Keep 4096-dimensional embeddings as the current quality baseline rather
    than prescribing lower dimensions.
  - Separate quality targets from future performance optimization decisions.
- `ARCHITECTURE.md`
  - Describe the implemented genre-aware analysis modules and artifacts.
  - Describe the search layer as it exists now, including 4096-dimensional
    exact vector search, keyword `ILIKE` paths, absent ANN indexes, and the
    distinction between internal search modules and exposed CLI commands.
  - Do not present planned hybrid retrieval as already implemented.
- `docs/USER_MANUAL.md`
  - Regenerate command coverage from `nm --help` and each subcommand help.
  - Remove commands that are documented but not registered: `nm search event`,
    `nm storage sync-all`, `nm storage reset`, `nm validate schema`, and
    `nm validate all`.
  - Document `nm pipeline insights`, `nm search insight`, and
    `nm validate insights` as implemented commands.
  - Correct Python support to 3.10 or newer.
  - Add a known-limitations section for search behavior that is implemented but
    not yet reliable enough to describe as hybrid or fully semantic retrieval.
- `AGENTS.md` and `CLAUDE.md`
  - Synchronize shared rules and command lists.
  - Keep only the agent name and skill directory platform-specific.
  - Correct the Codex skill path to `.agents/skills/`.
  - Remove claims that current `nm search chapter` is semantic by default.
  - Use configuration files, rather than a hard-coded model name, as the source
    for the active model.
  - Include the implemented insights stage without making it mandatory for
    every pipeline mode.
- `docs/GENRE_AWARE_ANALYSIS.md`
  - Link it into the active documentation map.
  - Replace model-name assumptions with capability-based wording and point to
    `config/providers.yaml` for the active provider.
- `docs/feedback.md`
  - Keep unresolved feedback only.
  - Remove completed documentation-cleanup requests after this work is
    verified.
- `src/novel_material/storage/migrations/README.md`
  - Ensure both existing migration files appear in the execution order and
    history.

### Delete

- `docs/CLAUDE_CODE_SETTINGS.md`: generic Claude Code reference material that is
  unrelated to Novel Material behavior and has no inbound project links.
- `docs/classify_implementation.md`: completed implementation proposal whose
  current behavior belongs in the architecture and user manual.
- `docs/superpowers/plans/2026-06-16-genre-aware-analysis-profiles.md`: completed
  implementation plan superseded by code and `docs/GENRE_AWARE_ANALYSIS.md`.
- `docs/superpowers/plans/2026-06-20-word-count-contract-fix.md`: completed task
  plan superseded by tests and Git history.
- `docs/superpowers/specs/2026-06-20-word-count-contract-design.md`: completed
  narrow design superseded by the established word-count contract and tests.
- `docs/code-review-report.md`: retain its current deletion; confirmed issues
  are either fixed, represented in active documentation, or will be covered by
  the retrieval implementation plan.

### Preserve Without Rewriting

- `docs/feedback/archive/*.md`: historical project memory used by the feedback
  archive workflow.
- `data/tag-system/*.md`: subsystem contract documentation outside the general
  `docs/` hierarchy.
- `.agents/skills/*/SKILL.md` and `.claude/skills/*/SKILL.md`: skill behavior is
  outside this documentation-only change, apart from fixing references to it.

## Verification

The documentation pass is complete only when:

1. `python -m pytest -q` still reports `73 passed, 1 skipped` or a newer clean
   baseline caused by unrelated concurrent work.
2. The command inventory in `docs/USER_MANUAL.md`, `AGENTS.md`, and `CLAUDE.md`
   matches the output of:
   - `nm --help`
   - `nm pipeline --help`
   - `nm search --help`
   - `nm tags --help`
   - `nm material --help`
   - `nm storage --help`
   - `nm validate --help`
3. Every relative Markdown link in retained active documentation resolves to an
   existing file.
4. Searches for stale claims no longer find:
   - Python 3.8 support.
   - universal two-second retrieval.
   - `nm search event` as an exposed command.
   - `nm storage sync-all` or `nm storage reset` as exposed commands.
   - `nm validate schema` or `nm validate all` as exposed commands.
   - current chapter search described as semantic by default.
5. `AGENTS.md` and `CLAUDE.md` differ only in their platform-specific agent name
   and skill path.
6. Existing unrelated changes to `config/providers.yaml` remain untouched.

## Non-Goals

- Do not implement retrieval changes in this documentation pass.
- Do not change the database schema or migrate embeddings.
- Do not restore `docs/code-review-report.md`.
- Do not rewrite feedback archives or tag-system contracts.
- Do not promise that planned quality improvements already exist.
