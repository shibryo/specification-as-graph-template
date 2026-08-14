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
- **Implementation freedom is explicit.** A specification states what must remain true while identifying mechanisms that may vary.
- **Reference implementations are not the specification.** Existing code may demonstrate one conforming realization without silently becoming normative.
- **SPEC.md is a narrative projection.** Rendering resolves graph references into names and reconstructs a coherent system-level explanation rather than dumping records.
- **Chapters cut the narrative by subject domain.** When the subject spans more than one domain, `spec/chapters.yaml` groups interactions, interfaces, invariants, failures, and the lifecycle into reader-facing chapters. Type-ordered sections are only the fallback for single-topic subjects.

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
  chapters.yaml        Optional subject-domain chapter layer
examples/
  symphony-scheduling/ Worked example: a spec recovered from an existing codebase
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

`examples/symphony-scheduling/` demonstrates the template applied as a function to an existing implementation: the scheduling/orchestration subsystem of [openai/symphony](https://github.com/openai/symphony) was recovered from its Elixir source alone (without reading its hand-written SPEC.md) into a specification graph, then validated and rendered:

```bash
make validate DIR=examples/symphony-scheduling/spec
make render   DIR=examples/symphony-scheduling/spec
```

The rendered `examples/symphony-scheduling/SPEC.md` projects four subject-domain chapters (state machine; polling, scheduling, and dispatch; retry and reconciliation; workspace management and safety), each assembling its interactions, interfaces, lifecycle, invariants, and failure semantics in reading order.

## What a complete specification should make possible

A competent implementation agent should be able to determine:

- why the subject exists;
- which concepts define its model;
- which responsibilities own semantic decisions;
- how major interactions proceed end to end;
- how state changes over time;
- what must remain invariant;
- what failures mean and how recovery is constrained;
- which interface semantics must be preserved;
- which implementation choices are intentionally free;
- how a reference implementation maps onto the specification without becoming the specification.

The target is not a comprehensive inventory of observed details. The target is a coherent implementation contract for the subject as a whole.
