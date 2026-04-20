# DoD-Grade Advanced Capability Roadmap

Date: 2026-03-30
Repo: `cameo-mcp-bridge`
Prompt: How should this product evolve to handle advanced MBSE/DoD/UAF/OOSEM work, including diagram-specific needs like fishbone layout, compartment visibility, and use-case subject containment?

## Grounding

The current product is a strong generic Cameo automation bridge, not yet a methodology-aware MBSE platform.

What it already does well:
- Generic element CRUD, stereotypes/profiles, relationships, diagrams, specifications, and macros
- Diagram shape listing, placement, movement, deletion, path creation, and property setting
- Large-model containment browsing via paginated child listing
- Session-wrapped structured writes on the Swing EDT

What the recent transcript exposed:
- Diagram intent is still too low-level. Fishbone diagrams, Values compartment visibility, and use-case subject containment all require presentation semantics, not just model CRUD.
- Safety is not strong enough for high-stakes use. Macro-driven extension wiring can trigger model inconsistency, timeout behavior is ambiguous, and plugin/server skew is only detected after failure.
- Scale support exists, but mostly as guardrails rather than a full large-model contract.
- The repo has almost no notion of `viewpoint`, `artifact`, `method phase`, `conformance`, or `evidence`.

## Survivors

These are the strongest ideas after combining and filtering the subagent outputs.

### 1. Capability Negotiation and Health Handshake

Add a first-class capability endpoint and require the Python MCP server to verify it before exposing tools.

Why this survives:
- It solves a real failure already seen in the field: new MCP tool exists on the Python side, but the running plugin 404s because the Java side is older.
- It is low-complexity and immediately reduces operator confusion.

Core payload:
- plugin version/build hash
- MCP server version/build hash
- supported endpoints/tools
- supported element/relationship/diagram types
- limits, timeout defaults, pagination support
- macro engine availability
- project open/dirty/session state

### 2. Presentation Control Primitives

Make diagram automation first-class instead of forcing callers to guess Cameo property names and shape containment rules.

Why this survives:
- It directly addresses the most painful gaps from the transcript.
- It turns brittle one-off macros into durable product features.

Priority APIs:
- `cameo_get_shape_properties`
- `cameo_set_shape_compartments`
- `cameo_place_elements`
- `cameo_reparent_shapes`
- `cameo_set_usecase_subject`
- `cameo_route_paths`
- `cameo_add_freeform_shapes`

Outcome:
- Fishbone diagrams become possible
- Values compartment visibility becomes robust
- Use-case subject rectangles become controllable without manual cleanup

### 3. Semantic Layout Recipes

Go one layer above `auto-layout` and add named layout profiles that operate on modeling intent.

Why this survives:
- Raw geometry is not enough for analyst-grade artifacts.
- This is the bridge between generic tooling and methodology-aware outputs.

Initial recipes:
- `fishbone`
- `hierarchical`
- `subject-with-usecases`
- `swimlane`
- `traceability-ladder`

Core API:
- `cameo_apply_layout_profile(profile, scopePresentationId?, direction?, spacing?)`

### 4. High-Stakes Safety Mode

Introduce a governed mutation mode for enterprise and DoD use.

Why this survives:
- Current safety posture is good enough for local dev, not for governance-grade work.
- The transcript already showed model inconsistency risk from unsafe operations.

Must-have features:
- dry-run/preflight for all mutating tools
- operation receipts and idempotency keys
- timeout reconciliation via operation status lookup
- checkpoint/rollback before destructive actions
- explicit approvals for macros and dangerous writes
- immutable audit trail

### 5. Large-Model Browse and Query Contract

Finish the scale story end-to-end instead of relying on one paginated containment endpoint.

Why this survives:
- DoD/UAF models get large fast.
- Token overflow is already a real problem in current usage.

Must-have features:
- pagination and filters on `cameo_query_elements`
- field projection and `view=compact|standard|full`
- token-safe summary endpoints
- stable sort and `hasMore`/cursor support
- out-of-band delivery for large images and heavy exports

### 6. Viewpoint Pack Registry

Define methodology packs for OOSEM, UAF, and DoD-style workflows.

Why this survives:
- This is the step that turns infrastructure into a product.
- The bridge already has enough primitives to support a first wave of packs.

Each pack should define:
- required profiles/stereotypes
- allowed artifact types
- naming rules
- mandatory relationships
- review checklist
- default layout recipes

### 7. Artifact Recipes and Workflow Engine

Add one-call builders for common artifacts and guide the operator through method phases.

Why this survives:
- Users should not have to remember the exact sequence of 20 generic calls.
- This is the fastest route to real product value after the primitives land.

Examples:
- OOSEM stakeholder needs package
- OOSEM logical architecture package
- UAF OV-5b activity artifact
- requirements satisfaction chain
- verification evidence scaffold

### 8. Conformance and Evidence Bundles

Validate artifacts and produce review-ready deliverables.

Why this survives:
- Advanced environments care about evidence, not just mutation success.
- It complements the workflow engine and safety mode.

Outputs:
- conformance results
- coverage gaps
- trace matrices
- before/after diagram images
- changed elements and assumptions
- Markdown/HTML review packet

## Rejected or Deferred

These ideas are not bad, but they are weaker than the survivors right now.

- Real-time model change notifications
Reason: useful later, but less urgent than capability negotiation, safety, and scale.

- Multi-user remote service with auth as a primary investment
Reason: the repo is explicitly local-first; making it networked before it is safe and methodology-aware is premature.

- More raw macro power
Reason: the product already has too much unsafe escape hatch and not enough governed structure.

## Recommended Order

### Today / Immediate

1. Add capability negotiation and version handshake.
2. Add `get_shape_properties` and `set_shape_compartments`.
3. Make `cameo_add_to_diagram` return `presentationId`.
4. Add pagination/filtering to `cameo_query_elements`.

### Next 1-2 Weeks

1. Add `reparent_shapes`, `set_usecase_subject`, and `route_paths`.
2. Add dry-run/preflight for destructive writes.
3. Add token-safe summaries and partial views.
4. Add operation receipts plus timeout reconciliation.

### Next 2-6 Weeks

1. Ship the first layout recipes: `fishbone`, `subject-with-usecases`, `hierarchical`.
2. Ship the first viewpoint pack: `OOSEM`.
3. Add artifact recipes for guided OOSEM workflows.
4. Add evidence bundle export.

### Quarter-Scale

1. Add async jobs and chunked delivery for heavy operations.
2. Add UAF/DoD viewpoint packs.
3. Add conformance validation and cross-view coverage analysis.
4. Add immutable audit trail and approval-gated high-stakes mode.

## Product Thesis

The right move is not “more endpoints.”

The right move is:

1. Finish the low-level presentation and scale primitives.
2. Make the bridge safe and negotiable.
3. Layer methodology-aware packs and artifact recipes on top.
4. Add validation and evidence so the output is reviewable.

That is how the product moves from “generic Cameo bridge” to “advanced MBSE automation platform for real OOSEM/UAF/DoD workflows.”

## Phase 1 Moonshot: Best AI Cameo Operator

### Grounding in Current Repo Reality

This repo already has the right substrate for an operator product:
- a direct local bridge into Cameo's Java API rather than an external sync layer
- broad structured coverage across elements, relationships, diagrams, specifications, and image export
- session-wrapped writes on the EDT for normal operations
- early large-model support through paginated containment browsing

But it is still infrastructure, not yet an operator:
- the Python MCP server is mostly a thin proxy over HTTP handlers
- status only returns plugin/version/port, so tool and plugin skew is discovered after failure
- diagram support is mostly geometry and property writes, not modeling-intent or presentation-semantics control
- macros remain the escape hatch, with self-managed sessions and a fixed 60-second timeout
- test coverage is still minimal, which is not enough for a high-trust modeling operator

### Phase Objective

Make `cameo-mcp-bridge` the fastest and safest way for one expert modeler to turn intent into correct Cameo changes, diagram updates, and review evidence without falling back to Groovy for routine work.

The win condition for Phase 1 is not "full DoD platform." The win condition is that an advanced user can treat the AI as a dependable Cameo operator for high-value daily tasks inside a local live session.

### Product Thesis

Phase 1 should win the operator loop before it wins the methodology stack.

If the product can:
- understand what the model and diagram currently look like
- expose what it is capable of before the user starts work
- execute structured, presentation-aware mutations safely
- return receipts, before/after evidence, and next-step context

then it becomes the best AI Cameo operator even before OOSEM/UAF packs are fully built. The methodology layer can compound on top of that foundation in later phases.

### Target Users

- Senior systems engineers and MBSE practitioners who already spend most of their day in Cameo.
- OOSEM/UAF/DoD-style modelers who need to produce reviewable artifacts under time pressure.
- AI-native technical teams who are comfortable with a local-first workflow but need higher trust than "run a macro and hope."

### Core Capabilities

1. Capability-aware startup and health.
   The bridge should declare its exact tool surface, limits, versions, macro availability, and project/session state before the MCP client exposes tools.

2. Token-safe large-model situational awareness.
   The operator should be able to browse and query large models with compact views, paging, stable limits, and summaries that fit into an LLM loop.

3. Presentation-aware diagram control.
   The operator should understand shapes, compartments, containment, and routing as first-class concepts rather than forcing users into raw coordinates and guessed property names.

4. Governed mutation.
   Mutations should support dry-run/preflight, operation receipts, timeout reconciliation, and explicit guardrails for destructive actions and macros.

5. Evidence-producing execution.
   Every important operation should be able to produce before/after images, changed element lists, and a concise explanation of what happened.

6. Narrow artifact recipes for repeated analyst work.
   Phase 1 should ship a few sharp operator recipes around real pain points instead of a broad workflow engine.

### What to Build

1. Capability negotiation and tool gating.
   Add a first-class capability endpoint plus Python-side verification so version skew is detected before a broken tool is exposed.

2. An operator-grade mutation envelope.
   Add dry-run, operation IDs, receipts, status lookup, and consistent error classes for all mutating endpoints. Make macro execution approval-gated and report session/time-out state explicitly.

3. A real large-model contract.
   Extend query/browse endpoints with paging, projection, compact views, stable ordering, and token-safe summaries. The current containment pagination is a start, not the finish line.

4. Presentation inspection and control primitives.
   Add `get_shape_properties`, return `presentationId` from `cameo_add_to_diagram`, and add structured APIs for shape reparenting, subject containment, compartment visibility, and path routing.

5. Three operator recipes that prove the wedge.
   - `use-case subject setup`: create a clean use case diagram with subject boundary containment and predictable placement.
   - `values/compartment control`: inspect and toggle relevant compartments without macro guessing.
   - `fishbone or causal review layout`: produce a review-ready diagram from model elements using a named layout recipe instead of manual drag-and-drop.

6. A minimal evidence bundle.
   For targeted recipes and important writes, return changed elements, assumptions, before/after diagram images, and a compact review packet.

7. Contract and regression testing for the bridge surface.
   Phase 1 needs a real compatibility harness across Python tools and Java handlers. The current test footprint is too small to support a trust-heavy positioning.

### What Not to Build in Phase 1

- A multi-user cloud service, auth layer, or remote orchestration platform.
- Full OOSEM, UAF, or DoD methodology packs with broad conformance rules.
- A generic "build any diagram from any prompt" autonomy pitch.
- More open-ended macro power as the primary answer to missing structured tools.
- Heavy background job infrastructure unless a concrete Phase 1 recipe truly needs it.
- Formal evidence management systems beyond a lightweight review packet.

### Moat

The moat is not "we have MCP."

The moat is the combination of:
- direct embedded access to Cameo's live model and presentation layer
- structured operator loops that remove the need for brittle one-off macros
- safety and evidence features that make the AI usable in serious modeling environments
- a growing library of high-value Cameo-specific recipes that competitors cannot fake with generic SysML chat

If Phase 1 is done well, the product becomes the default AI operator for existing Cameo experts. That is the right wedge before expanding into methodology packs, governance suites, and broader enterprise workflows.

### Risks

- Presentation semantics in Cameo are brittle; some diagram behaviors may vary by element type or Cameo version.
- Safety features can slow down the loop if they are implemented as bureaucracy instead of fast preflight.
- The team could over-invest in ambitious methodology framing before the operator basics are reliable.
- Sparse automated coverage makes plugin/server skew and regression risk materially higher today.
- Fishbone-quality layout may be harder than subject containment or compartment control, so the recipe scope needs disciplined acceptance criteria.

### Exit Criteria

Phase 1 is done when all of the following are true:

1. A new MCP session performs capability handshake first, and incompatible tools are withheld before the user can call them.
2. Core mutating operations support dry-run/preflight plus a receipt with enough detail to reconcile timeouts and partial-failure reports.
3. The operator can inspect and modify diagram presentation state without macros for the target wedge workflows.
4. The system can complete the three proof workflows below end-to-end with structured tools and review evidence:
   - build a use case diagram with correct subject containment
   - inspect and change compartment visibility in a repeatable way
   - produce one named review-ready layout recipe with no manual cleanup beyond minor cosmetic adjustment
5. Large-model browsing and querying can stay within token budget for real projects through compact views and paging.
6. There is a bridge compatibility/regression harness that covers the Phase 1 contract across Python and Java, not just a unit test around response formatting.

## Phase 2 Moonshot: Best OOSEM/UAF Copilot

Phase 2 starts only after Phase 1 has landed the bridge fundamentals: capability handshake, presentation-control primitives, safer writes, and a real large-model browse/query contract. The goal is not to become a generic “AI for Cameo.” The goal is to become the best copilot for analysts who already work in OOSEM, UAF, and adjacent DoD-style workflows.

### Phase Objective

Turn the bridge from a tool catalog into a methodology-aware copilot that can help an analyst plan, create, validate, and package OOSEM/UAF artifacts with far less manual Cameo work and far less methodology recall burden.

In plain terms:
- Phase 1 makes the bridge reliable enough.
- Phase 2 makes it opinionated enough.

### Product Thesis

The winning product is not a chat agent that happens to call Cameo.

The winning product is a methodology-aware copilot that:
- understands what phase of OOSEM/UAF work the user is in
- knows which artifacts are expected next
- can build those artifacts using structured bridge operations rather than raw macros
- checks the output for conformance, coverage, and review readiness
- produces evidence a lead systems engineer can actually trust

The repo is already strong at generic CRUD, relationships, diagrams, specifications, and image export. That means Phase 2 should not start by adding more low-level endpoints. It should add a thin but opinionated product layer above the existing bridge: packs, recipes, validations, and evidence.

### Target Users

Primary:
- Systems engineers using Cameo for OOSEM-style analysis who know the method but do not want to manually drive every modeling step
- DoD and defense-adjacent teams producing reviewable architecture artifacts under time pressure
- Small MBSE teams that need analyst leverage more than they need enterprise platform plumbing

Secondary:
- UAF practitioners who need guided creation of operational, services, and traceability artifacts
- Technical leads or reviewers who need evidence bundles, coverage checks, and change receipts more than raw model mutation power

Not the initial target:
- casual UML users
- teams looking for a multi-user cloud modeling platform
- organizations whose main problem is enterprise auth, workflow routing, or repository sync

### Core Capabilities

1. Method-aware workspace

The copilot should maintain explicit context for:
- methodology pack in use: `OOSEM`, then `UAF`
- current phase or workstream
- target artifact set
- modeling assumptions, open gaps, and pending review items

This is the missing layer between chat prompts and raw bridge calls.

2. Viewpoint and artifact recipes

The copilot should offer named builders for common artifacts, not generic “create some elements” behavior.

Examples:
- OOSEM stakeholder needs package
- OOSEM use case model with explicit subject containment
- OOSEM activity/behavior decomposition starter
- OOSEM logical architecture scaffold
- UAF operational activity or traceability artifact starter

Each recipe should encode:
- required element types and stereotypes
- expected containment structure
- expected diagrams
- preferred layout recipe
- minimum conformance checks

3. Guided refinement loops

Phase 2 should make iterative analyst workflows first-class:
- plan artifact from prompt
- generate scaffold
- inspect diagram/specification output
- ask focused follow-up questions for ambiguity
- patch the model safely
- re-run validations and export review evidence

The current repo already supports the underlying loop with query, create, modify, diagram, specification, and image tools. Phase 2 productizes it.

4. Conformance and coverage checking

The copilot must tell the user what is missing, not just what was created.

Checks should include:
- required artifact presence
- required relationships present or missing
- naming and containment rule compliance
- stereotype/profile usage
- coverage across viewpoints where Phase 2 can detect it
- explicit assumptions and unresolved gaps

5. Review-ready evidence bundles

Every serious workflow should be able to emit a compact review packet with:
- what changed
- which artifacts were touched or created
- before/after diagram images where available
- conformance results
- uncovered gaps
- the assumptions the copilot made

This is how the product becomes credible in high-stakes environments without pretending to replace human review.

### What to Build

Build the thinnest product layer that sits above the current bridge and proves real analyst leverage.

1. Ship a pack system, not a giant hard-coded assistant

Add a first-class pack registry in the Python server for methodology packs, starting with `OOSEM` and keeping `UAF` narrow at first. A pack should declare:
- artifact recipes
- required profiles/stereotypes
- layout defaults
- validation rules
- evidence template sections

2. Ship a stateful copilot workflow contract

Add a workflow abstraction in the MCP layer for:
- selecting a pack
- selecting a target artifact or phase
- generating a scaffold plan before mutation
- executing structured steps through existing bridge tools
- storing receipts, assumptions, and validation results

This can begin as explicit MCP tools plus structured JSON state. It does not need a heavyweight agent runtime.

3. Ship 3-5 excellent OOSEM recipes

Do not attempt full OOSEM coverage immediately. Start with a small set that maps well onto the current repo surface:
- stakeholder needs / mission context scaffold
- use case package with actors, use cases, includes/extends, and subject containment support
- activity decomposition scaffold
- logical architecture starter with blocks, properties, ports, and trace links
- review packet export for one completed artifact set

4. Ship conformance checks that use current reality

Leverage what the bridge already exposes today:
- element queries
- relationship queries
- specification reads
- diagram shape inspection
- diagram image export

Avoid checks that require deep repository-wide semantics the repo cannot yet inspect cheaply or safely.

5. Ship evidence as a default output, not an optional add-on

If a recipe mutates the model, it should also be able to summarize:
- operations performed
- artifacts affected
- validation pass/fail
- images generated
- gaps handed back to the analyst

### What Not to Build

Do not build these in Phase 2:
- a hosted collaboration platform
- remote multi-user orchestration as the center of the strategy
- autonomous “design the whole architecture for me” black-box generation
- broad support for every DoDAF/UAF viewpoint at once
- more macro-centric power as the primary escape hatch
- deep enterprise governance features before the conformance/evidence loop is strong

Reason:
- the repo is still local-first, localhost-only, and thinly tested
- the moat is methodology-aware leverage on top of a real Cameo bridge, not generic enterprise platform surface area
- broad scope here would create a weak product with impressive demos and low trust

### Moat

If this works, the moat is a stack, not a single feature.

1. Native control of a real Cameo model

The bridge already has direct access to the Cameo JVM and OpenAPI rather than screen-scraping or generic file transforms. That is a real foundation.

2. Methodology packs encoded as executable product behavior

OOSEM/UAF know-how becomes reusable software:
- artifact recipes
- layout defaults
- conformance rules
- evidence templates

That is much harder to copy than “chat over documentation.”

3. Reviewability

In this domain, trust comes from showing work:
- receipts
- validations
- images
- explicit assumptions

Evidence turns the copilot from a clever assistant into a tool a lead engineer can sign off on.

4. Grounded feedback loop from real model state

Because the copilot can inspect containment, specifications, relationships, and diagrams, it can reason over actual model state instead of only prompt text. That creates a tighter learning and workflow loop than generic LLM copilots.

### Risks

1. The methodology layer outruns the bridge layer

If Phase 1 primitives are incomplete, Phase 2 recipes will collapse back into brittle macros and manual cleanup.

2. Diagram presentation remains a trust killer

The repo still has known nested-presentation limitations in diagram handling. If the copilot creates method-correct but visually poor artifacts, users will treat it as a toy.

3. Too much methodology breadth too early

Trying to cover OOSEM, UAF, and broader DoD process in one pass will produce shallow packs and weak validation.

4. Validation quality is too weak to matter

If conformance checks only restate obvious counts, the product will not earn reviewer trust.

5. Safety and test depth lag product claims

Today the repo has minimal automated tests and an unsafe macro escape hatch. Phase 2 messaging must not imply governance-grade assurance unless the product actually has it.

### Crisp Exit Criteria

Phase 2 is complete when all of the following are true:

1. A user can choose `OOSEM` and complete at least three end-to-end artifact workflows through named recipes rather than ad hoc prompting.

2. At least one narrow `UAF` pack exists and can generate a useful starter artifact plus validation output without depending on raw macro authoring.

3. Every Phase 2 recipe emits:
- operation receipts
- assumptions
- conformance results
- a compact evidence bundle with artifact and diagram references

4. The copilot can explain what is missing from an artifact package in methodology terms, not just API terms.

5. The dominant happy path uses structured bridge operations; macros are an exception path, not the product.

6. A systems engineer can go from prompt to review packet for a bounded OOSEM workflow in one session with materially less manual Cameo cleanup than today.

7. The doc set and product language clearly position the system as a methodology-aware local copilot built on the existing bridge, not as a fully autonomous MBSE platform.

### Strategic Readout

Phase 2 should be the point where the product stops competing on “number of endpoints” and starts competing on “quality of methodological assistance.”

If Phase 1 makes the bridge dependable, Phase 2 should make it indispensable for bounded OOSEM/UAF work.

## Phase 3 Moonshot: Classified-Ready MBSE Platform

This phase should only start after the earlier roadmap items land. Right now the repo is still a localhost bridge with no authentication, an unrestricted macro escape hatch, minimal tests, and no first-class concepts for viewpoint, conformance, approval, or evidence. Phase 3 is therefore not “add classified features” on top of the current stack. It is the point where the bridge becomes a governable MBSE operating layer for controlled enclaves.

### Phase Objective

Turn `cameo-mcp-bridge` from a powerful local automation bridge into a policy-governed, offline-deployable MBSE platform that can be reviewed for use in classified and other high-assurance environments.

### Product Thesis

The winning product is not a cloud MBSE copilot for defense.

It is a workstation- and enclave-friendly control plane for Cameo that:
- keeps the current local-first architecture advantage
- replaces implicit trust with explicit policy, approvals, and evidence
- packages methodology-aware workflows as governed artifacts instead of free-form prompts
- produces reviewable outputs that fit RMF, design assurance, and program-audit expectations

In other words: keep the repo's strongest property, direct access to the real Cameo model on a local box, and add the controls that make that access acceptable in high-trust programs.

### Target Users

- Digital engineering leads inside defense primes and major subs who need repeatable UAF/DoD/OOSEM workflows in Cameo
- Chief engineers and MBSE leads on classified or export-controlled programs where internet-dependent tooling is a non-starter
- Government lab, FFRDC, and program office teams that need traceable model changes and evidence packages, not just automation
- Toolsmith teams responsible for hardening and standardizing MBSE workflows across secured enclaves

### Core Capabilities

- Policy-enforced mutation: every write, macro, and export runs through policy checks, approval rules, and operation receipts
- Governed methodology packs: UAF, DoDAF-adjacent, and OOSEM packs define allowed artifacts, required relationships, naming rules, and review checks
- Evidence-native operation: each artifact build emits conformance results, assumptions, changed elements, and review bundles by default
- Offline and enclave packaging: deterministic builds, pinned dependencies, no internet requirement, and installation/update flow that works inside disconnected environments
- Role-aware operating modes: analyst, reviewer, and admin paths with different permissions and approvals, even if the first version implements this locally rather than as a multi-user web service
- Large-model safe workflows: chunked export, projected queries, job receipts, and resumable operations for real program-scale models

### What To Build

- A capability and policy handshake that extends the planned version handshake into a deployment contract:
  - plugin/server build IDs
  - enabled tool families
  - macro policy state
  - approval requirements
  - supported methodology packs
  - logging/audit configuration
- A signed or at least tamper-evident audit ledger for all mutating operations with:
  - operator identity/source
  - tool invoked
  - inputs
  - affected element IDs
  - before/after summary
  - approval record
  - rollback/checkpoint reference
- Macro containment:
  - disabled by default in classified mode
  - allowlist by script hash or named recipe
  - explicit approval path for exceptions
  - eventual migration of common macro use cases into structured tools
- Methodology packs as code, not docs:
  - UAF/DoD pack
  - OOSEM pack
  - conformance rules
  - artifact recipes
  - evidence templates
- Review-packet generation:
  - conformance summary
  - trace gaps
  - changed artifacts
  - before/after diagram images
  - machine-readable manifest for program records
- Deployment hardening for offline enclaves:
  - reproducible build/install path
  - dependency pinning
  - explicit no-network mode
  - local admin configuration for policy and pack loading

### What Not To Build

- Do not pivot into a cloud-hosted defense SaaS. The repo's advantage is direct local integration with Cameo on locked-down workstations.
- Do not make multi-user collaboration or remote browser UIs the centerpiece of this phase. Governance matters more than surface area.
- Do not expand arbitrary macro power. The current macro tool is already the main trust-boundary problem.
- Do not try to become a full PLM/ALM replacement, document management system, or TWC clone.
- Do not promise “accredited for classified use” as a product claim. The credible target is “ready for enclave deployment review and program-specific hardening.”

### Moat

- Direct embedded access to the real Cameo API, not a toy model layer or detached exporter
- Local-first architecture that naturally fits disconnected and tightly controlled environments better than cloud copilots
- A governed workflow stack sitting above raw model CRUD: methodology packs, policy controls, evidence bundles, and conformance checks
- Institutional memory encoded as executable packs and artifact recipes, which is much harder to copy than adding a few more endpoints

### Risks

- The current trust boundary is too loose. `cameo_execute_macro` has filesystem and JVM-level power, and the plugin has no auth layer today.
- The current quality bar is too low for this phase. Test coverage is minimal, and failure recovery still relies on session reset and operator judgment.
- “Classified-ready” can drift into compliance theater if the product ships checklists without real enforcement, provenance, and auditability.
- Cameo desktop/plugin constraints may limit how far approval workflows and identity can go without an external broker or local companion service.
- UAF/DoD pack design can sprawl into consultingware if the first packs are not opinionated, narrow, and tied to real review artifacts.

### Crisp Exit Criteria

- The bridge can run fully offline on a locked-down workstation with Cameo 2024x and complete core workflows without internet access.
- Every mutating operation produces a durable receipt with actor, action, affected elements, before/after summary, and rollback reference.
- Macros are off by default in classified mode, and any allowed macro execution is hash-allowlisted and approval-gated.
- At least one `OOSEM` pack and one `UAF/DoD` pack can create, validate, and export a review packet for a representative end-to-end artifact set.
- Reviewers can reconstruct what changed, why it changed, and whether it passed conformance checks without opening the prompt transcript.
- The product is ready for enclave deployment review because policy, logging, packaging, and no-network operation are productized rather than left to local setup folklore.
