# CATIA Magic / Cameo Feature Access Ranking

Last updated: 2026-05-04

Assumption: the dictated name "Keisha" means CATIA Magic / Cameo Systems Modeler / MagicDraw in this bridge context.

## Purpose

Rank the CATIA Magic / Cameo feature universe by engineering value, then map each feature to the current MCP/REST access level. This is a working control document for deciding which bridge capabilities to implement next.

The first hard target is the top 100 features. The expectation is that the top 100 should eventually be either fully accessible through typed MCP tools or explicitly marked as intentionally out of scope.

## Source Base

Primary official sources used for this first pass:

- Dassault Cameo Systems Modeler product page: requirements management, traceability, reports, parametrics, distributed use, SysML requirements, matrices, requirement tables, numbering, and simulation/trade-study claims.
  - https://www.3ds.com/products/catia/no-magic/cameo-systems-modeler
- Dassault No Magic MBSE page: system requirements, analysis/simulation, design, V&V, collaboration, publishing, report generation.
  - https://www.3ds.com/products/catia/no-magic/model-based-systems-engineering
- CATIA Magic documentation landing page: current product areas across modeling, collaboration, simulation, Alf, concept modeling, RTC, EE architecture, and virtual twin.
  - https://docs.nomagic.com/spaces/CATIA/pages/47102202/CATIA+Magic+Documentation
- SysML Plugin diagram descriptions: requirement, BDD, IBD, package, parametric, sequence, state machine, activity, use case, views/viewpoints, matrices, relation maps, requirement table, blackbox ICD, whitebox ICD.
  - https://docs.nomagic.com/spaces/SYSMLP2024x/pages/136725489/Diagram+descriptions
- MagicDraw Generic Table documentation: property editing, element creation, derived properties, custom columns.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227149612/Generic+table
- MagicDraw Validation documentation: validation suites, rules, selected-scope validation, results panel, markers, solver suggestions, pre-commit validation.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227152141/Validation
- MagicDraw Metric Table documentation: model metrics, metric suites, metric definitions, validation-based metrics, export.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227149699/Metric+table
- MagicDraw criteria documentation: dependency matrix criteria, relation map criteria, smart package queries, traceability expressions, derived properties, structured expressions, legend conditions.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227151652/Getting+started+with+specifying+criteria
- Cameo Simulation Toolkit project options: animation, simulation framework, sequence diagram generation, fUML, parametric evaluator, SCXML, script engine.
  - https://docs.nomagic.com/spaces/CST2024xR3/pages/227175253/Project+options
- Report Wizard documentation: report templates and output formats including txt, rtf, html, odt, odf, odp, docx, xlsx, pptx, XML.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227153542/Generating+Reports+from+Report+Wizard
- Collaborative modeling documentation: Teamwork Cloud repository, users, permissions, versions, commits, updates, locks, branches.
  - https://docs.nomagic.com/spaces/MD2024xR3/pages/227152361/Collaborative+modeling
- Cameo DataHub documentation: import/export, synchronization, references across MagicDraw, SysML Plugin, UPDM, DOORS, ENOVIA TRM, and CSV.
  - https://docs.nomagic.com/spaces/CDH2024xR3/overview

## Current MCP Baseline

Live bridge checked on 2026-05-04:

- Plugin: `CameoMCPBridge`
- Version: `2.3.5`
- Health: `ok`
- REST capabilities advertised: `79`
- Status evidence:
  - [live-status-for-feature-access-map.json](../../mcp-server/validation-output/live-status-for-feature-access-map.json)
  - [live-capabilities-for-feature-access-map.json](../../mcp-server/validation-output/live-capabilities-for-feature-access-map.json)

Current strong MCP areas:

- Project/status/capability readback
- UI state, active diagram, and selection readback
- Element query/get/create/modify/delete
- Containment tree readback
- Stereotype/profile/tagged value application
- Relationship create/read
- Native matrix list/get/create for current supported matrix kinds
- Generic table list/get/create
- Diagram list/create/add/export/layout/shape/path/presentation repair
- Diagram and presentation property dumps
- Relation Map list/get/create/configure/settings/criteria/traceability graph/render/verify/compare
- Snapshot and diff evidence capture
- Controlled probes
- Specification window get/set
- Macro execution as an escape hatch
- MCP-only methodology guidance, semantic verifiers, review packets, proofing, and export assembly helpers

Coverage codes:

- `strong`: typed MCP/REST access exists and has been exercised or is directly implemented.
- `partial`: meaningful access exists, but is incomplete, fragile, macro-backed, or missing native parity.
- `missing`: no stable typed MCP/REST access found.
- `risky`: access exists but has known CATIA instability or semantic risk.

## Ranked Top 100

| Rank | Feature | Category | Value | MCP Coverage | Evidence / Gap |
|---:|---|---|---:|---|---|
| 1 | Requirement element create/read/update/delete | Requirements | 5 | strong | Element CRUD plus `Requirement` type support. |
| 2 | Requirement text, id, and specification fields | Requirements | 5 | strong | `cameo_get_specification`, `cameo_set_specification`, element modify. |
| 3 | Requirement hierarchy and containment | Requirements | 5 | strong | Containment tree and relationship support. |
| 4 | Derive requirement relationships | Requirements | 5 | strong | Native relationship support and live Relation Map criteria. |
| 5 | Refine relationships | Requirements | 5 | strong | Native relationship support and live Relation Map criteria. |
| 6 | Satisfy relationships | Requirements | 5 | strong | Native relationship support, satisfy matrix, Relation Map criteria. |
| 7 | Verify relationships | Requirements | 5 | partial | Relationship type exists; full test-case execution/verification workflow missing. |
| 8 | Trace relationships | Requirements | 5 | strong | Relationship create/read and traceability graph support. |
| 9 | Requirement-to-design traceability | Requirements | 5 | strong | Relationships, matrices, relation maps, custom verifiers. |
| 10 | Requirement-to-test traceability | Requirements | 5 | partial | Verify links possible; test management/execution is not first-class. |
| 11 | Requirement coverage and gap analysis | Requirements | 5 | strong | Matrices, Relation Maps, traceability graph, custom checks. |
| 12 | Requirement quality checks | Requirements | 5 | strong | MCP `cameo_verify_requirement_quality`. |
| 13 | Requirement change impact analysis | Requirements | 5 | strong | Relation Maps, snapshots, graph diff. |
| 14 | Requirement Diagram creation and population | Requirements | 5 | partial | Diagram create/add works; full palette/layout semantics need per-diagram validation. |
| 15 | Requirement Table | Requirements | 5 | partial | Generic table access exists; native Requirement Table specifics need endpoint parity. |
| 16 | Automated requirement numbering | Requirements | 5 | missing | Official feature; no typed MCP endpoint found. |
| 17 | Requirement number uniqueness check | Requirements | 5 | partial | Could be custom verifier; no native active uniqueness endpoint. |
| 18 | Requirements import/export | Requirements | 5 | missing | No ReqIF/DataHub/file roundtrip endpoint. |
| 19 | DataHub requirement synchronization | Requirements | 5 | missing | DataHub not exposed except possible macro. |
| 20 | Requirement review and approval packet | Requirements | 5 | partial | MCP review packet helper exists; not Cameo Collaborator parity. |
| 21 | Block element modeling | Architecture | 5 | strong | `Block` element type support. |
| 22 | Block Definition Diagram | Architecture | 5 | partial | Diagram creation/population supported; full BDD symbol semantics need validation matrix. |
| 23 | Internal Block Diagram | Architecture | 5 | partial | Diagram creation/population supported; nested presentation fidelity remains partial. |
| 24 | Package Diagram | Architecture | 5 | partial | Generic diagram support; package model support strong. |
| 25 | Part properties | Architecture | 5 | strong | Property element support. |
| 26 | Value properties | Architecture | 5 | partial | Property/DataType support exists; value-specific UI behavior not complete. |
| 27 | Flow properties | Architecture | 5 | strong | `FlowProperty` support and flow-property validation memory. |
| 28 | Ports | Architecture | 5 | strong | `Port` element support. |
| 29 | Proxy/full port presentation semantics | Architecture | 5 | partial | Ports exist; full SysML port display semantics need UI-proven property endpoints. |
| 30 | Interface blocks | Architecture | 5 | strong | `InterfaceBlock` support. |
| 31 | Connectors | Architecture | 5 | strong | Connector relationship/path support. |
| 32 | Item flows | Architecture | 5 | strong | ItemFlow relationship support plus item-flow label controls. |
| 33 | Associations | Architecture | 5 | strong | Relationship support. |
| 34 | Composition relationships | Architecture | 5 | strong | Relationship support. |
| 35 | Generalization relationships | Architecture | 5 | strong | Relationship support. |
| 36 | Logical architecture allocation | Architecture | 5 | strong | Allocate relationships and allocation matrices. |
| 37 | Physical architecture allocation | Architecture | 5 | strong | Allocate relationships and allocation matrices. |
| 38 | Allocation Matrix | Architecture | 5 | strong | Native matrix kind supported. |
| 39 | Port boundary consistency checks | Architecture | 5 | strong | MCP semantic verifier. |
| 40 | Blackbox ICD Table | Architecture | 5 | partial | Official table type; generic table access exists but native ICD endpoint missing. |
| 41 | Whitebox ICD Table | Architecture | 5 | partial | Official table type; generic table access exists but native ICD endpoint missing. |
| 42 | Activity elements | Behavior | 5 | strong | Activity type support. |
| 43 | Action elements | Behavior | 5 | strong | Activity/action node types supported. |
| 44 | Control flows | Behavior | 5 | strong | Relationship support. |
| 45 | Object flows | Behavior | 5 | strong | Relationship support. |
| 46 | Activity parameters and pins | Behavior | 5 | partial | Some activity node types exist; full pin/parameter contracts need expansion. |
| 47 | Activity partitions / swimlanes | Behavior | 5 | strong | Native partition route was implemented and live-validated. |
| 48 | Activity Diagram creation and layout | Behavior | 5 | partial | Diagram support strong; full activity-specific layout needs more validation. |
| 49 | Activity flow semantic verification | Behavior | 5 | strong | MCP semantic verifier. |
| 50 | State machine elements | Behavior | 5 | strong | `StateMachine` and `State` support. |
| 51 | State Machine Diagram | Behavior | 5 | partial | Diagram support plus state helpers; composite/nested state presentation still partial. |
| 52 | Transition relationships | Behavior | 5 | strong | Transition support. |
| 53 | Transition triggers | Behavior | 5 | strong | MCP transition trigger get/set helpers. |
| 54 | Guards and effects | Behavior | 5 | partial | Likely specification fields; no dedicated guard/effect typed endpoint. |
| 55 | State entry/do/exit behaviors | Behavior | 5 | strong | MCP state behavior helpers. |
| 56 | Use case elements | Behavior | 4 | strong | UseCase and Actor type support. |
| 57 | Actor elements | Behavior | 4 | strong | Actor type support. |
| 58 | Use case subject binding | Behavior | 4 | strong | `cameo_set_usecase_subject`. |
| 59 | Use Case Diagram | Behavior | 4 | partial | Diagram support; use-case-specific presentation needs validation. |
| 60 | Sequence Diagram | Behavior | 4 | partial | Listed official diagram; deep sequence presentations remain a known gap. |
| 61 | Lifelines and messages | Behavior | 4 | missing | No first-class typed endpoint found. |
| 62 | Behavior-to-structure allocation | Behavior | 5 | strong | Allocate relationships, matrices, custom checks. |
| 63 | Constraint blocks | Parametrics | 5 | strong | `ConstraintBlock` element type support. |
| 64 | Parametric Diagram | Parametrics | 5 | partial | Official diagram; diagram support exists, solver/control missing. |
| 65 | Constraint properties and parameters | Parametrics | 5 | partial | Elements/properties possible; no dedicated parametric authoring API. |
| 66 | Binding connectors | Parametrics | 5 | partial | Connector support exists; parametric binding semantics need validation. |
| 67 | Parametric model solving | Parametrics | 5 | missing | Official feature; no typed solver endpoint. |
| 68 | System measures of effectiveness | Parametrics | 5 | missing | No typed MoE/trade-study endpoint. |
| 69 | Parametric trade studies | Parametrics | 5 | missing | Paramagic/trade-study flow not exposed. |
| 70 | What-if scenarios | Parametrics | 5 | missing | No typed scenario endpoint. |
| 71 | External solver integration | Parametrics | 4 | missing | MATLAB/Mathematica/OpenModelica integration not exposed. |
| 72 | Excel/sensor-driven parametric inputs | Parametrics | 4 | missing | No data-source bridge endpoint. |
| 73 | fUML activity simulation | Simulation | 5 | missing | Simulation Toolkit not exposed as typed MCP. |
| 74 | SCXML state machine simulation | Simulation | 5 | missing | Simulation Toolkit not exposed as typed MCP. |
| 75 | Simulation animation | Simulation | 4 | missing | No simulation UI/control endpoint. |
| 76 | Simulation validation and verification | Simulation | 5 | missing | Native simulation V&V not exposed. |
| 77 | Simulation sequence diagram recording | Simulation | 4 | missing | No typed endpoint. |
| 78 | Simulation script engine | Simulation | 4 | missing | Macro exists, but not Simulation Toolkit script control. |
| 79 | Relation Map creation/configuration | Traceability | 5 | strong | Typed Relation Map endpoints. |
| 80 | Relation Map raw settings dump | Traceability | 5 | strong | Evidence-gathering endpoint. |
| 81 | Relation Map criteria templates | Traceability | 5 | partial | Live-proven for key SysML relationships; long tail remains. |
| 82 | Relation Map traceability graph | Traceability | 5 | strong | Graph traversal endpoint. |
| 83 | Relation Map render/export | Traceability | 4 | partial | No-refresh render safe; native refresh/render presentation remains partial. |
| 84 | Relation Map compare | Traceability | 4 | strong | Typed compare endpoint. |
| 85 | Predefined Relation Maps | Traceability | 4 | partial | Can create/configure; native preset catalog not fully exposed. |
| 86 | Dependency Matrix criteria | Traceability | 5 | partial | Matrix support exists; full criteria expression UI parity incomplete. |
| 87 | Satisfy Matrix | Traceability | 5 | strong | Native matrix kind supported. |
| 88 | Allocation Matrix | Traceability | 5 | strong | Native matrix kind supported. |
| 89 | Derive Requirement Matrix | Traceability | 5 | strong | Native matrix kind supported. |
| 90 | Refine Matrix | Traceability | 5 | strong | Native matrix kind supported. |
| 91 | Verify Matrix | Traceability | 5 | missing | Relationship exists; native verify matrix creation not confirmed. |
| 92 | Smart Package queries | Querying | 4 | missing | Criteria docs cover this; no typed endpoint. |
| 93 | Structured expression criteria | Querying | 4 | partial | Relation Map criteria support exists; broad expression builder absent. |
| 94 | Simple Navigation operation | Querying | 4 | missing | No generic expression endpoint. |
| 95 | Metachain Navigation operation | Querying | 4 | missing | No generic expression endpoint. |
| 96 | Find operation | Querying | 4 | partial | Relation Map criteria work touched this area; no generic endpoint. |
| 97 | Implied Relations operation | Querying | 4 | missing | No generic expression endpoint. |
| 98 | Derived properties | Querying | 4 | missing | Generic Table docs feature; no typed endpoint. |
| 99 | Custom table columns | Querying | 4 | missing | Generic Table docs feature; no typed endpoint. |
| 100 | Snapshot/diff evidence capture | Review / Evidence | 5 | strong | Custom MCP snapshot/diff endpoints. |

## Long-Tail Feature Backlog

These are not less real; they are ranked below the initial top 100 because they are either more specialized, more presentation/admin oriented, or dependent on one of the top-100 access layers.

| Approx. Rank | Feature | Category | Current Coverage |
|---:|---|---|---|
| 101 | Generic Table create/list/get | Tables | strong |
| 102 | Generic Table property editing | Tables | partial |
| 103 | Generic Table element type configuration | Tables | partial |
| 104 | Generic Table filling criteria | Tables | partial |
| 105 | Glossary Table | Tables | missing |
| 106 | Instance Table | Tables | missing |
| 107 | Metric Table | Metrics | missing |
| 108 | Metric suites | Metrics | missing |
| 109 | Metric parameter definitions | Metrics | missing |
| 110 | Metric definitions | Metrics | missing |
| 111 | Validation-based metric definitions | Metrics | missing |
| 112 | Metrics recalculation | Metrics | missing |
| 113 | Metric export to HTML/XLSX/CSV | Metrics | missing |
| 114 | Model progress metrics | Metrics | partial |
| 115 | Native validation suites | Validation | missing |
| 116 | Native validation rule execution | Validation | missing |
| 117 | Active validation suites | Validation | missing |
| 118 | Requirements validation suites | Validation | partial |
| 119 | SysML validation suites | Validation | partial |
| 120 | Custom validation rules | Validation | missing |
| 121 | Validation Results panel readback | Validation | missing |
| 122 | Validation marker bar readback | Validation | missing |
| 123 | Solver suggestions for invalid elements | Validation | missing |
| 124 | Pre-commit validation | Validation | missing |
| 125 | Diagram list/create | Diagram Authoring | strong |
| 126 | Add model element to diagram | Diagram Authoring | strong |
| 127 | Diagram image export | Diagram Authoring | strong |
| 128 | Auto layout | Diagram Authoring | strong |
| 129 | Shape inventory | Diagram Authoring | strong |
| 130 | Shape property dump | Diagram Authoring | strong |
| 131 | Shape move | Diagram Authoring | strong |
| 132 | Shape delete | Diagram Authoring | strong |
| 133 | Shape property set | Diagram Authoring | strong |
| 134 | Shape compartment set | Diagram Authoring | strong |
| 135 | Transition label presentation | Diagram Authoring | strong |
| 136 | Item-flow label presentation | Diagram Authoring | strong |
| 137 | Allocation compartment presentation | Diagram Authoring | strong |
| 138 | Hidden label repair | Diagram Authoring | strong |
| 139 | Label position repair | Diagram Authoring | strong |
| 140 | Conveyed item label repair | Diagram Authoring | strong |
| 141 | Compartment preset normalization | Diagram Authoring | strong |
| 142 | Presentation pruning | Diagram Authoring | strong |
| 143 | Path decoration pruning | Diagram Authoring | strong |
| 144 | Shape reparenting | Diagram Authoring | strong |
| 145 | Path routing | Diagram Authoring | strong |
| 146 | Diagram visual verification | Diagram Authoring | strong |
| 147 | Views and Viewpoints Diagram | Viewpoint Modeling | partial |
| 148 | Diagram legends | Diagram Authoring | missing |
| 149 | Legend item conditions | Querying | missing |
| 150 | Diagram frame/name/type/owner display options | Diagram Authoring | partial |
| 151 | Teamwork Cloud repositories | Collaboration | missing |
| 152 | Teamwork Cloud user/permission readback | Collaboration | missing |
| 153 | Server project open/update | Collaboration | missing |
| 154 | Commit changes | Collaboration | missing |
| 155 | Project version history | Collaboration | missing |
| 156 | Tags/comments on versions | Collaboration | missing |
| 157 | Element locking | Collaboration | missing |
| 158 | Lock-free editing status | Collaboration | missing |
| 159 | Branch creation | Collaboration | missing |
| 160 | Branch/trunk navigation | Collaboration | missing |
| 161 | Model merge | Collaboration | missing |
| 162 | Merge conflict inspection | Collaboration | missing |
| 163 | Merge result accept/reject | Collaboration | missing |
| 164 | Differences report | Collaboration | missing |
| 165 | Project usages/libraries | Collaboration | partial |
| 166 | Report Wizard generation | Reports | missing |
| 167 | Report template discovery | Reports | missing |
| 168 | Report template variables | Reports | missing |
| 169 | DOCX report output | Reports | missing |
| 170 | XLSX report output | Reports | missing |
| 171 | PPTX report output | Reports | missing |
| 172 | HTML/Web Publisher output | Reports | missing |
| 173 | Attached report template synchronization | Reports | missing |
| 174 | Cameo Collaborator publishing | Reports / Review | missing |
| 175 | Cameo Collaborator review/approval | Reports / Review | missing |
| 176 | DataHub import/export | Integration | missing |
| 177 | DataHub synchronization | Integration | missing |
| 178 | DOORS synchronization | Integration | missing |
| 179 | ENOVIA TRM synchronization | Integration | missing |
| 180 | CSV synchronization | Integration | missing |
| 181 | ReqIF import/export | Integration | missing |
| 182 | XMI import/export | Integration | missing |
| 183 | FMI/co-simulation exchange | Integration | missing |
| 184 | 3DEXPERIENCE collaboration integration | Integration | missing |
| 185 | External reference/link management | Integration | partial |
| 186 | Profiles | Customization | strong |
| 187 | Stereotypes | Customization | strong |
| 188 | Tagged values | Customization | strong |
| 189 | Stereotype metaclasses | Customization | strong |
| 190 | DSL stereotype display modes | Customization | partial |
| 191 | Profile authoring workflow | Customization | partial |
| 192 | Custom DSL element creation | Customization | partial |
| 193 | Custom validation suite authoring | Customization | missing |
| 194 | Script operations | Customization | missing |
| 195 | Opaque behavior structured expressions | Customization | partial |
| 196 | Macro execution | Automation | risky |
| 197 | Controlled script probes | Automation | strong |
| 198 | Environment options | UI / Settings | missing |
| 199 | Project options | UI / Settings | missing |
| 200 | Simulation project options | Simulation | missing |
| 201 | Active diagram readback | UI / Settings | strong |
| 202 | UI selection readback | UI / Settings | partial |
| 203 | UI state readback | UI / Settings | strong |
| 204 | Specification window read/write | UI / Settings | strong |
| 205 | Model browser invalid markers | UI / Settings | missing |
| 206 | General search/find UI | UI / Settings | missing |
| 207 | Model compare local projects | Collaboration | missing |
| 208 | Model libraries | Model Management | partial |
| 209 | Project save | Project | strong |
| 210 | Project dirty-state readback | Project | strong |
| 211 | Session reset | Project | strong |
| 212 | Controlled undo/redo | Project | missing |
| 213 | Project templates | Project | missing |
| 214 | SysML-Lite perspective switching | UI / Settings | missing |
| 215 | Expert/full-featured perspective switching | UI / Settings | missing |
| 216 | Methodology recipe guidance | Methodology | strong |
| 217 | Methodology recipe validation | Methodology | strong |
| 218 | Methodology review packet | Methodology | partial |
| 219 | Methodology wizard execution | Methodology | missing |
| 220 | UAF/DoDAF/MODAF/NAF viewpoints | Enterprise Architecture | partial |
| 221 | Magic Systems of Systems Architect features | Enterprise Architecture | partial |
| 222 | Magic Cyber Systems Engineer features | Cyber / SoS | partial |
| 223 | Magic Software Architect features | Software Architecture | partial |
| 224 | Magic Systems EE Architect features | Electrical / Electronics | missing |
| 225 | Magic Alf Analyst | Executable Modeling | missing |
| 226 | Magic Concept Modeler | Concept Modeling | missing |
| 227 | Magic Real-Time Communication Designer | RTC | missing |
| 228 | Virtual Twin of the Organization | Enterprise / Digital Twin | missing |
| 229 | Model publishing to images | Publishing | strong |
| 230 | Model publishing to documents | Publishing | partial |
| 231 | Model publishing to web views | Publishing | missing |
| 232 | Design-progress dashboards | Metrics | partial |
| 233 | Custom model QA dashboards | Metrics | partial |
| 234 | Gap-analysis dashboards | Metrics | partial |
| 235 | Automated model repair plans | QA / Repair | strong |
| 236 | Proofing model text | QA / Repair | strong |
| 237 | Applying proofing patch plans | QA / Repair | partial |
| 238 | Cross-diagram inconsistency detection | QA / Repair | strong |
| 239 | Cross-diagram remediation planning | QA / Repair | strong |
| 240 | Required diagram export | Deliverables | strong |
| 241 | PPT/PDF assembly | Deliverables | partial |
| 242 | Model artifact completeness comparison | Deliverables | strong |
| 243 | Containment tree navigation | Navigation | strong |
| 244 | Element relationship readback | Navigation | strong |
| 245 | Element property dump | Inspection | strong |
| 246 | Presentation property dump | Inspection | strong |
| 247 | Raw relation-map setting diffing | Inspection | strong |
| 248 | Human UI snapshot comparison | Inspection | strong |
| 249 | Capability manifest introspection | Inspection | strong |
| 250 | Bridge/plugin version compatibility check | Inspection | strong |

## Current Top Implementation Gaps

1. Native simulation and parametric execution APIs.
2. Native validation suite runner and validation result readback.
3. Requirements import/export, numbering, and native requirement table parity.
4. Teamwork Cloud / Magic Collaboration Studio operations.
5. Report Wizard and Cameo Collaborator publishing/review.
6. DataHub / ReqIF / DOORS / CSV synchronization.
7. Generic criteria expression builder for matrices, relation maps, tables, smart packages, legends, and derived properties.
8. Deep diagram-specific presentation handlers for sequence diagrams, composite states, parametric diagrams, and view/viewpoint diagrams.
9. UI/environment/project option read/write, including simulation options and perspective switching.
10. Product-module-specific surfaces for Magic Systems of Systems Architect, Magic Cyber Systems Engineer, Magic EE Architect, Alf Analyst, Concept Modeler, RTC Designer, and Virtual Twin.

## Recommended Execution Order

1. Turn the top 100 into tests: one live validation script per feature cluster.
2. Mark each top-100 row as `verified`, `implemented-not-live-verified`, `partial`, or `missing`.
3. Implement missing top-tier typed endpoints before broadening long-tail UI automation.
4. Keep macro execution as a diagnostic/prototyping escape hatch, then replace useful macros with typed Java endpoints.
5. Maintain this document as the feature backlog and create implementation issues from the top-gap list.
