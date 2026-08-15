# Specification-as-Graph Template

A generic template repository for specifications that are precise enough for an AI agent to implement while preserving whole-system meaning.

The core model is:

```text
Evidence -> Specification Graph -> Semantic Assembly -> SPEC.md
                              \-> AI implementation
```

`spec/` is authoritative. `SPEC.md` is a generated narrative projection.

The graph is intentionally centered on the subject model rather than a flat requirement list. Normative statements constrain concepts, responsibilities, interactions, lifecycle, interfaces, invariants, and failures instead of replacing them.

## Design principles

- **Model before requirements.** Describe the subject, its responsibilities, and how its parts interact before reducing it to normative constraints.
- **Interactions are first-class.** End-to-end behavior must connect participants, triggers, sequence, postconditions, invariants, and failures.
- **State is explicit when state matters.** Lifecycle semantics include an initial state, reachable transitions, and terminal states where applicable.
- **Failures are part of behavior.** Failures must be attached to the interactions in which they can occur and must define required recovery semantics.
- **Implementation freedom is explicit.** A specification states what must remain true while identifying mechanisms that may vary — and what a conforming implementation must document about its choice.
- **The operator contract is part of the subject.** Runtime-tunable behavior that changes normative semantics is recorded as parameters (`spec/parameters.yaml`): the parameter's existence and semantics are normative, its name and default are not.
- **Optional capabilities are extensions, not core.** Chapters and records marked `conformance: extension` may be omitted entirely; an implemented extension is normative in full.
- **Verification is assembled, not hand-written.** Verification clauses on interactions and invariants project into a generated Test and Validation Matrix, grouped by chapter.
- **Redundancy is generated, never authored.** Implementation-facing aids — the config cheat sheet, the implementation checklist, concept field lists, examples, and non-normative reference algorithms — are projections of the same records as the body, so they cannot drift the way hand-written summaries do.
- **Two implementers, one document.** The rendered SPEC.md serves a transcribing implementer (scan path: contracts, tables, checklists, examples) and a reconstructing implementer (understanding path: intent, model, chapters) at once, and opens with a reading guide that routes each to its path.
- **Provenance shapes normativity.** A spec declares whether it is `recovered` from an implementation or `owned` by the subject's authors, and each invariant records its basis (observed / stated / derived). Observed-only mechanisms are presumed implementation-defined; owners may fix the mechanisms they chose.
- **Basis is checkable, not self-assessed.** The observe step writes an evidence register (`spec/evidence.yaml`) of what the recovery actually used, pinned to a reference anchor. Records cite entries, and validation checks each invariant's basis against the cited evidence kinds.
- **Reference implementations are not the specification.** Existing code may demonstrate one conforming realization without silently becoming normative.
- **SPEC.md is a narrative projection.** Rendering resolves graph references into names and reconstructs a coherent system-level explanation rather than dumping records.
- **Chapters cut the narrative by subject domain.** When the subject spans more than one domain, `spec/chapters.yaml` groups interactions, interfaces, invariants, failures, and the lifecycle into reader-facing chapters. Type-ordered sections are only the fallback for single-topic subjects.
- **Only the analytical front is fixed.** Problem Statement, Goals and Non-Goals, System Overview, and Core Domain Model open every generated document the same way. Everything after them is positioned by the subject: a chapter claims the lifecycle and the configuration field list where they belong. A record type that can only be collected into a section of its own is a defect in the graph, not a section the subject asked for.
- **Rationale has no record type.** Reasons are written where the thing they justify is written: whole-subject boundaries in the Problem Statement, a chapter's reason in its overview, a record's reason on the record. A separate list of design intents can only be dumped into a section nobody asked for, and it pre-announces the invariants that state the same facts one section later.
- **Labels name the list, not the record type.** Any list can be named by its record with `<field>_label`. A document that prints the same handful of type-derived labels dozens of times has told the reader its sections are interchangeable.

## Repository structure

```text
.spec/
  process.yaml        Authoring and recovery protocol
  render.yaml         Narrative projection contract
  schema/             Machine-readable schema foundations
spec/
  manifest.yaml
  intent.yaml
  model.yaml
  responsibilities.yaml
  interactions.yaml
  lifecycle.yaml
  interfaces.yaml
  invariants.yaml
  failures.yaml
  implementation-defined.yaml
  reference.yaml
  chapters.yaml        Optional chapter layer, cut by component
  parameters.yaml      Optional operator contract layer
  evidence.yaml        Optional evidence register (what the recovery used)
examples/
  symphony/            Worked example: a spec recovered clean-room from an existing codebase
AGENTS.md              Mandatory agent behavior
SPEC.md                Generated specification
requirements.txt       Renderer dependency
```

## Source of truth

The structured files under `spec/` are the source of truth.

`SPEC.md` MUST NOT be edited directly. It exists to provide a coherent projection of the complete specification and may be regenerated at any time.

An implementation agent may read either the structured graph or the rendered `SPEC.md`. The two representations must preserve the same semantics.

## Workflow

```text
Observe
  -> Reconstruct
  -> Infer intent
  -> Classify
  -> Normalize into connected records
  -> Validate graph and whole-system coverage
  -> Render narrative SPEC.md
  -> Review under-specification and over-specification
```

Run:

```bash
python -m pip install -r requirements.txt
make validate
make render
make check
```

`make validate` checks graph integrity and whole-system structure. It intentionally rejects several forms of disconnected specification data, such as unreachable lifecycle states, unreferenced invariants, failures that are not connected to interactions, or responsibilities that do not participate in end-to-end behavior. When chapters are declared, it also rejects unresolved or duplicated chapter membership and warns about records that belong to no chapter.

`make render` regenerates `SPEC.md`.

`make check` fails when `SPEC.md` is stale.

The tools work as a function over any specification graph directory: pass `DIR=<path>` (or `--dir <path>` to `tools/spec.py`) to validate and render another subject, e.g. a spec recovered from an existing codebase. `SPEC.md` is written next to the given directory.

## Worked example

`examples/symphony/` demonstrates the template applied as a function to an existing implementation: the whole [openai/symphony](https://github.com/openai/symphony) service was recovered clean-room from its Elixir source and tests alone — the recovering agent was forbidden from reading the project's hand-written SPEC.md and documentation — into a specification graph, then validated and rendered:

```bash
make validate DIR=examples/symphony/spec
make render   DIR=examples/symphony/spec
```

The rendered `examples/symphony/SPEC.md` projects eight chapters — six core and two optional extensions — each assembling its interactions, interfaces, lifecycle, invariants, and failure semantics in reading order. Compared against the project's own hand-written specification, the clean-room recovery reproduces its structure and operator contract, and additionally captures behavior the hand-written document lacks (the blocked-on-operator-input lifecycle state, symlink-escape workspace containment).

## What a complete specification should make possible

A competent implementation agent should be able to determine:

- why the subject exists;
- which concepts define its model;
- which responsibilities own semantic decisions;
- which parameters an operator must be able to set, and what each governs;
- how major interactions proceed end to end;
- how state changes over time;
- what must remain invariant;
- what failures mean and how recovery is constrained;
- which interface semantics must be preserved;
- which capabilities are optional extensions and which are core;
- which implementation choices are intentionally free, and which of them must be documented;
- how conformance is verified;
- how a reference implementation maps onto the specification without becoming the specification.

The target is not a comprehensive inventory of observed details. The target is a coherent implementation contract for the subject as a whole.
