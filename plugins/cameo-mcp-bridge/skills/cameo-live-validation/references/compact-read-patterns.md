# Compact Read Patterns

- Prefer `view="compact"` when querying elements or containment children.
- Scope queries to the narrowest useful package or type.
- For large trees, page with `cameo_list_containment_children` instead of reading the recursive tree.
- Read matrix lists and summary counts before fetching a full matrix payload.
- For diagrams, request metadata first and only fetch rendered images when a visual check is necessary.
- Keep Codex answers focused on findings, blockers, and next actions rather than raw JSON dumps.
