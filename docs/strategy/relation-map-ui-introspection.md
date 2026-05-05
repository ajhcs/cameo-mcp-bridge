# Relation Map UI Introspection

These tools exist to observe CATIA Magic's native diagram/UI state before
attempting relation-map mutation. Use them when the model graph is traversable
but a rendered Relation Map shows only the context node or legend.

## Inspect Current UI State

1. Open the target diagram in CATIA Magic.
2. Select the relevant shape or path.
3. Call `cameo_get_ui_state`, or use the smaller `cameo_get_active_diagram` and
   `cameo_get_ui_selection` tools.
4. Use returned `diagram.id` and `presentationId` values as inputs to property
   dumps.

Raw HTTP equivalents:

```text
GET /api/v1/ui/state
GET /api/v1/ui/active-diagram
GET /api/v1/ui/selection
```

The UI endpoints are best-effort because CATIA selection APIs vary by version.
Always check `warnings` before treating an empty selection as proof that nothing
is selected.

## Dump Settings And Properties

Use these readback tools before and after a human changes the diagram through
CATIA Magic's UI:

```text
GET /api/v1/inspect/diagrams/{diagramId}/properties
GET /api/v1/inspect/diagrams/{diagramId}/presentations/{presentationId}/properties
GET /api/v1/relation-maps/{relationMapId}/settings/raw
GET /api/v1/relation-maps/{relationMapId}/presentations
```

Defaults favor summaries. Increase scope intentionally with `includeRaw=true`,
`includePresentationProperties=true`, `limit`, and `offset`.

## Snapshot And Diff Workflow

1. Create a snapshot of the bridge-created or failing Relation Map:

```json
POST /api/v1/snapshots
{
  "targetType": "relationMap",
  "targetId": "<relation-map-id>",
  "name": "before-ui-change",
  "includeRaw": false,
  "includePresentations": true,
  "includeProperties": true
}
```

2. In CATIA Magic, change one UI setting, criterion, or expansion state.
3. Create a second snapshot with a different `name`.
4. Diff the snapshots:

```json
POST /api/v1/snapshots/diff
{
  "beforeSnapshotId": "<before-id>",
  "afterSnapshotId": "<after-id>",
  "includeDetails": true,
  "maxChanges": 500
}
```

Interpretation:

- `relationMapSettings.dependencyCriteria` changes point to native criteria
  strings or objects that should be made into stable tools.
- `presentationCount` or `presentationCountsByType` changes show expansion or
  rendering effects.
- A passing traceability graph with unchanged presentation count means CATIA's
  native Relation Map renderer still has not expanded, even if model
  relationships exist.

## Validation Commands

```bash
git status --short
cd plugin
bash ./gradlew -PcameoHome=/mnt/d/DevTools/CatiaMagic build
cd ../mcp-server
python3 -m pytest
```

Live validation still requires CATIA Magic running with the plugin deployed and
a project open. After deploying a rebuilt plugin, restart CATIA Magic before
trusting UI-state or raw-settings results.

## Native Refresh Safety

Live validation on the `13A Stakeholder-to-Physical Traceability Map` showed
that CATIA Magic's native `RelationshipMapUtilities.refreshMap(Diagram)` can
block the Swing EDT for longer than normal bridge request timeouts. A timeout
from the bridge does not mean CATIA canceled the underlying EDT work.

For that reason, Relation Map refresh is deliberately opt-in:

- `render`, `criteria`, `expand`, `collapse`, `create`, and `configure` do not
  request native refresh unless `refresh=true` is provided.
- plain render/export runs as an EDT read without a model write session when no
  refresh, expand, or layout mutation is requested.
- `POST /api/v1/relation-maps/{relationMapId}/refresh` remains available for
  deliberate refresh attempts and accepts `refreshTimeoutSeconds`.
- do not run parallel write requests against CATIA. The bridge serializes model
  writes and reports an in-progress write instead of allowing overlapping
  `SessionManager` sessions.

Use refresh only when you need CATIA's native UI state to rebuild, and prefer
the graph/verify/render evidence path below for regression validation.

Run the broad read-only validation first:

```bash
cd mcp-server
python3 scripts/live_validate_ui_introspection.py \
  --base-url http://127.0.0.1:18740/api/v1 \
  --relation-map-id <relation-map-id> \
  --output validation-output/ui-introspection.json
```

For a controlled write validation, pass `--allow-write` and either a raw
UI-derived criterion or a template key:

```bash
python3 scripts/live_validate_ui_introspection.py \
  --base-url http://127.0.0.1:18740/api/v1 \
  --relation-map-id <relation-map-id> \
  --allow-write \
  --criteria-template satisfy.sourceToTarget \
  --criteria-mode append
```

Run the focused rendering regression script when you know the expected graph and
render counts:

```bash
python3 scripts/live_validate_relation_map_rendering.py \
  --base-url http://127.0.0.1:18740/api/v1 \
  --relation-map-id <relation-map-id> \
  --root-element-id <root-element-id> \
  --relationship-type Satisfy \
  --expected-min-graph-nodes 2 \
  --expected-min-graph-edges 1 \
  --expected-min-rendered-presentations 2 \
  --output-dir validation-output/relation-map-rendering
```

That script writes `raw-settings.json`, `criteria-probe.json`,
`presentations.json`, `graph.json`, `render.json`, `verify.json`,
`snapshot-diff.json`, and `summary.json`; if image export succeeds it also
writes `rendered.png`.

By default, the rendering script avoids native refresh. Pass `--refresh` only
when the test is specifically about CATIA native refresh behavior, and expect it
to be a long-running write operation.

## Mutation And Verification

After a UI-created delta has been captured, use the stable mutation endpoints:

```text
GET  /api/v1/relation-maps/criteria/templates
PUT  /api/v1/relation-maps/{relationMapId}/criteria
POST /api/v1/relation-maps/{relationMapId}/expand
POST /api/v1/relation-maps/{relationMapId}/collapse
POST /api/v1/relation-maps/{relationMapId}/render
POST /api/v1/relation-maps/{relationMapId}/verify
POST /api/v1/relation-maps/compare
```

`expand` and `collapse` are intentionally receipt-heavy. If CATIA Magic does not
expose a public expansion method in the installed version, the endpoint reports
`supported=false` and includes the reflected method attempts instead of
pretending the UI state changed.

Use probe templates when normal endpoints do not expose enough API evidence:

```text
GET  /api/v1/probes/templates
POST /api/v1/probes/execute
```

Arbitrary scripts are refused by default; current probes are built-in read-only
reflection templates. For constrained discovery without arbitrary code, use
`language=javaReflection` with one of:

- `operation=listMethods` plus `className`
- `operation=invokeGraphSettingsGetter` plus `relationMapId` and `methodName`
- `operation=invokeStaticNoArg` plus `className` and `methodName`

Allowed reflection class names are restricted to CATIA/MagicDraw package
prefixes used by the bridge.
