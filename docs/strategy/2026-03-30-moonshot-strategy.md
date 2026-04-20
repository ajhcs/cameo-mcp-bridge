# Moonshot Strategy

Date: 2026-03-30
Repo: `cameo-mcp-bridge`
Thesis: Move from a generic Cameo MCP bridge to a mission-grade MBSE operating system, starting with the narrowest wedge that can win: the best AI operator for Cameo-based systems engineering work.

## Executive Summary

The current repo already proves something important: a local-first Python-to-Java bridge can drive real Cameo model creation, diagram manipulation, stereotype/profile work, specification editing, and arbitrary macro execution. That is enough to be useful. It is not enough to be trusted for serious OOSEM/UAF/DoD work.

The moonshot path is:

1. Make the platform deterministic.
2. Make the platform presentation-aware.
3. Make the platform governable.
4. Make the platform methodology-aware.
5. Make the output reviewable enough that teams depend on it.

The mistake would be trying to jump directly to “DoD platform.” The right sequence is:

1. **Phase 1:** Best AI Cameo operator
2. **Phase 2:** Best OOSEM/UAF copilot
3. **Phase 3:** Classified-ready MBSE platform

## Grounding

Today the repo is strong on:
- generic element CRUD
- stereotypes, profiles, tagged values, and relationships
- diagram creation, placement, movement, deletion, and basic property control
- containment browsing with a large-model path
- local-first execution inside Cameo’s real Java API

Today the repo is weak on:
- capability negotiation and plugin/server version lockstep
- large-model query semantics beyond a few guarded endpoints
- presentation semantics like compartments, routing, reparenting, and freeform visual structure
- governance-grade safety, approvals, rollback, and auditability
- methodology-specific packs, recipes, conformance, and evidence
- automated test depth on safety-critical behavior

That means the winning strategy is not “more endpoints.” It is to raise the abstraction level in the right order.

## Sequencing Principles

These five principles should govern every phase:

1. Build contract before intelligence.
The bridge needs stable versioning, capability discovery, and query semantics before adding higher-level “smart” workflows.

2. Replace repeating macros with product primitives.
If users have to solve the same problem twice with Groovy, that problem belongs in the product.

3. Pull safety earlier than comfort suggests.
Higher-level automation multiplies blast radius. Governance cannot be a late polish pass.

4. Win one methodology deeply before expanding breadth.
OOSEM is the best first wedge. UAF/DoD breadth should come after one repeatable pack actually works.

5. Optimize for reviewable artifacts, not mutation throughput.
In this market, evidence is the product.

## Business Wedge

The initial wedge is not “AI for MBSE.” That is too vague.

The real wedge is:

**OOSEM artifact production in Cameo with manual cleanup removed and review packet generation built in.**

That wedge is attractive because:
- the users already live in Cameo
- the pain is acute and repetitive
- diagram cleanup and traceability are high-friction
- review quality matters more than raw generation speed
- the product can win without replacing the incumbent tool

If that wedge works, the moat compounds from three layers:
- deep Cameo execution knowledge
- presentation semantics that eliminate manual cleanup
- methodology-aware, reviewable outputs that are hard to reproduce with generic LLM agents

## Phase 1 Moonshot: Best AI Cameo Operator

### Objective

Become the most dependable way to operate Cameo with AI for real day-to-day modeling work.

This phase is about trust, determinism, and presentation control, not about becoming a full methodology platform yet.

### Product Thesis

The product should feel like a world-class operator sitting inside Cameo:
- it knows what the installed plugin can actually do
- it can browse large models without blowing up context
- it can manipulate shapes and symbol state reliably
- it can execute common mutations without relying on unsafe macro improvisation
- it can explain what it changed

If Phase 1 succeeds, users stop thinking “interesting bridge” and start thinking “this is the best way to drive Cameo.”

### Target Users

- systems engineers who already live in Cameo
- MBSE practitioners executing guided OOSEM/SysML workflows
- consultants building or refactoring SysML/UML artifacts
- internal toolsmiths trying to automate legacy Cameo-heavy workflows

### Core Capabilities

- capability handshake between Python MCP and Java plugin
- stable browse/query contract with pagination, filtering, and partial views
- better presentation identity and control:
  - return `presentationId` from shape placement
  - inspect shape properties
  - explicit compartment control
  - shape reparenting
  - path routing controls
- token-safe summaries for huge models and diagrams
- preflight and receipts for dangerous or ambiguous writes

### What To Build

1. Capability negotiation and health handshake.
2. Query contract completion: `limit`, filters, cursor/offset, compact/full views.
3. Presentation control primitives:
   - `get_shape_properties`
   - `set_shape_compartments`
   - `reparent_shapes`
   - `set_usecase_subject`
   - `route_paths`
4. Better operation semantics:
   - receipts
   - idempotency
   - timeout reconciliation
5. Replace repeated macro-only flows with productized handlers.

### What Not To Build

- cloud collaboration platform
- remote multi-user auth stack
- generic “agentic workflow” layer detached from Cameo realities
- broad UAF/DoDAF marketing before the operator layer is actually robust

### Moat

The moat in Phase 1 is execution quality:
- fewer brittle flows
- more deterministic presentation handling
- fewer version-skew failures
- fewer “manual fix in UI” moments

This is not a narrative moat. It is an operational moat.

### Risks

- staying a pile of endpoints instead of becoming an opinionated operator
- leaving macros as the dominant escape hatch
- underinvesting in tests for safety-sensitive flows
- adding more capabilities before tightening contract semantics

### Exit Criteria

Phase 1 is done when:
- plugin/server mismatches are detected before runtime failure
- large-model browsing is routine, not fragile
- common presentation tasks no longer require manual Cameo cleanup
- repeated macro workflows have been converted into product APIs
- users can complete non-trivial modeling sessions without losing trust in the bridge

## Phase 2 Moonshot: Best OOSEM/UAF Copilot

### Objective

Move from “best operator” to “best methodology-aware copilot,” starting with OOSEM and then expanding into UAF-style artifact systems.

This phase is about productizing engineering intent, not just tool control.

### Product Thesis

Users should stop having to remember which 20 primitive calls create a valid artifact set.

Instead, the product should understand:
- method phase
- artifact type
- required stereotypes/profiles
- expected trace patterns
- diagram conventions
- conformance rules
- evidence expectations

If Phase 2 succeeds, the product stops being just a Cameo bridge and becomes a real copilot for structured systems engineering work.

### Target Users

- OOSEM practitioners building workflow or program artifacts
- MBSE teams standardizing on repeatable artifact recipes
- early UAF adopters who need help producing consistent views
- engineering leads who care about traceability and review readiness

### Core Capabilities

- viewpoint pack registry
- OOSEM-first methodology pack
- artifact recipes and workflow engine
- semantic layout recipes
- conformance validators
- traceability and coverage analysis
- evidence bundle generation

### What To Build

1. Viewpoint pack registry.
Each pack defines:
- required profiles and stereotypes
- allowed artifact types
- naming rules
- mandatory relationships
- review checklist
- default layouts

2. OOSEM pack first.
Ship one deep pack before chasing breadth.

3. Artifact recipes.
Examples:
- stakeholder needs package
- system requirements package
- logical architecture package
- verification evidence scaffold

4. Workflow engine.
Track where the user is in the method and what is missing next.

5. Conformance and coverage.
Validate whether artifacts are merely present or actually correct.

6. Evidence bundles.
Export review packets with diagrams, trace, validation results, and assumptions.

### What Not To Build

- a giant generic “AI architect” abstraction with no method grounding
- simultaneous deep investment in OOSEM, UAF, DoDAF, and every other framework at once
- broad defense positioning before one methodology pack is obviously excellent

### Moat

The moat in Phase 2 is compound methodology intelligence:
- pack definitions
- recipes
- layout rules
- conformance logic
- evidence outputs

That body of knowledge is much harder to copy than raw endpoint access.

### Risks

- expanding framework breadth before proving depth
- automating workflows without strengthening safety
- creating pretty artifacts without meaningful conformance
- confusing “generated” with “review-ready”

### Exit Criteria

Phase 2 is done when:
- OOSEM work can be produced through pack-driven flows instead of ad hoc prompting
- the system can tell users what artifact is missing and why
- diagrams can be brought into conformance automatically for common cases
- evidence bundles are good enough to support real reviews
- users describe the product as a copilot for OOSEM/UAF work, not just an API bridge

## Phase 3 Moonshot: Classified-Ready MBSE Platform

### Objective

Become a policy-governed, offline-capable MBSE operating system suitable for secured enclaves and high-stakes engineering programs.

This phase is not about becoming a cloud defense chatbot. It is about becoming trusted infrastructure inside controlled environments.

### Product Thesis

In serious programs, the winning product is not the most generative one. It is the one that can be trusted:
- offline
- deterministic
- governable
- auditable
- reviewable
- adaptable across model backends and artifact systems

Phase 3 takes the local-first bridge and evolves it into a mission-grade control plane.

### Target Users

- defense and aerospace MBSE teams in controlled environments
- primes and integrators managing digital thread workflows
- program leads who need traceability, policy control, and review evidence
- enclave operators who need local execution, not SaaS dependency

### Core Capabilities

- high-stakes safety mode by default
- approvals and policy engine for mutations
- immutable audit trail
- checkpoint and rollback semantics
- async jobs and chunked delivery for heavy operations
- offline deployment and locked capability profiles
- multi-backend path beyond Cameo alone
- cross-view consistency and enterprise-scale evidence production

### What To Build

1. Policy-governed mutation plane.
Every dangerous action should be explainable, approvable, and traceable.

2. Immutable audit and receipts.
Persist operator, request, affected artifacts, policy path, and outcome.

3. Async job framework.
Heavy reads, exports, validations, and analysis should stop pretending to be synchronous.

4. Offline-first packaging.
Treat air-gapped and enclave deployment as a first-class requirement.

5. Pack expansion.
Only after OOSEM is deep and proven:
- UAF
- DoD-style review artifacts
- broader digital-thread coverage

6. Backend abstraction.
Cameo should remain a privileged backend, but not the only long-term one.

### What Not To Build

- public-cloud-first collaboration features as the main bet
- defense branding without policy-grade controls
- broad multi-backend abstraction before governance and pack semantics are stable

### Moat

The moat in Phase 3 is trust infrastructure:
- policy
- auditability
- enclave-friendly deployment
- pack-aware evidence production
- deep alignment with how real programs are reviewed and governed

This is much harder to copy than “we can also call the API.”

### Risks

- promising classified readiness before earning governance credibility
- keeping macros too central in critical paths
- failing to increase automated validation as stakes rise
- trying to become a general defense platform before owning one workflow deeply

### Exit Criteria

Phase 3 is done when:
- the product can run in offline or controlled environments without losing core value
- high-stakes mutations are policy-governed and auditable
- methodology packs produce artifacts and evidence that survive formal review
- teams view the product as infrastructure for program execution, not an assistant bolt-on

## Strategic Dependency Chain

The phases depend on each other tightly:

- capability negotiation is prerequisite to trust
- browse/query contract is prerequisite to large-model usability
- presentation primitives are prerequisite to semantic layouts
- safety receipts and preflight are prerequisite to workflow automation
- workflow automation is prerequisite to evidence bundles
- evidence bundles are prerequisite to high-stakes adoption

The right order is:

1. deterministic
2. expressive
3. governed
4. opinionated
5. enterprise-trusted

## Where This Can Fail

- The product remains a thin endpoint wrapper and never becomes methodology-aware.
- It adds more workflow abstraction before fixing trust, scale, and safety.
- It expands into UAF/DoD breadth before proving one strong OOSEM wedge.
- It treats review artifacts as a byproduct instead of the core deliverable.
- It assumes “agentic” behavior matters more than deterministic engineering outcomes.

## End-State Vision

The end-state is not “more MCP.”

The end-state is a system where a team can say:

“Produce the next valid artifact set for this engineering phase, bring the diagrams into conformance, show me the uncovered trace gaps, and generate the review packet with a complete audit trail.”

That is the point where the product stops being a bridge and becomes a platform.
