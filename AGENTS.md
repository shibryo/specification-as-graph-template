# Specification Agent Protocol

`spec/` is the source of truth. `SPEC.md` is generated and MUST NOT be edited directly.

Agents creating, recovering, or changing a specification MUST follow `.spec/process.yaml`.

## Primary rule

Do not document the implementation. Recover and specify the subject behind the implementation.

## Required behavior

1. Inspect available evidence before changing normative semantics.
2. Reconstruct the whole subject before writing isolated requirements.
3. Model concepts and their relationships where they are needed to explain meaning.
4. Model responsibilities and make semantic ownership explicit.
5. Model important end-to-end interactions, including trigger, participants, sequence, outcome, invariants, and failures.
6. Model lifecycle and state explicitly where state affects behavior.
7. Treat failure and recovery semantics as part of behavior rather than implementation detail.
8. Treat inferred design intent as uncertain until supported by evidence.
9. Separate essential semantics from implementation-specific or reference-specific choices.
10. Attach normative statements to the model element they constrain.
11. Do not create an unstructured requirements list as the primary specification model.
12. Group behavior records into subject-domain chapters (`spec/chapters.yaml`) when the subject spans more than one domain.
13. Run validation before rendering and regenerate `SPEC.md` after accepted changes.

## Narrative integrity rule

`SPEC.md` MUST explain the subject as a coherent whole.

The renderer MUST NOT degrade into concatenating records in storage order. It must reconstruct at least these views when relevant:

- problem and design intent;
- system model;
- responsibility and ownership model;
- end-to-end interactions;
- lifecycle and state transitions;
- interface semantics;
- invariants and constraints;
- failure and recovery model;
- implementation-defined freedom;
- reference implementation relationship;
- conformance expectations.

Chapter structure is part of narrative integrity. When the subject spans more than one domain, the graph MUST declare subject-domain chapters (`spec/chapters.yaml`) that group interactions, interfaces, invariants, and failures — and, where it belongs to one domain, the lifecycle — by theme, in reading order. The renderer projects chapters in declared order; records assigned to no chapter fall to an appendix and are reported by validation. Type-ordered projection is acceptable only for single-topic subjects.

Identifiers used by `spec/` are internal graph identity. The rendered specification SHOULD prefer semantic names and prose unless an identifier itself is necessary for external traceability.

## Abstraction rule

Prefer semantic requirements over mechanisms. A mechanism is normative only when the mechanism itself is intentionally part of the contract.

A requirement is too concrete when replacing an implementation mechanism would require changing the specification even though the intended semantics remain identical.

A requirement is too vague when an implementation can satisfy its literal wording while violating the documented design intent.

## Completion rule

A specification is not complete merely because all observed behaviors have been recorded.

Before completion, agents MUST perform both reviews:

### Under-specification review

Attempt to design an implementation that satisfies the written rules while violating the intended model, interactions, ownership, lifecycle, or failure semantics.

If such an implementation is possible, strengthen the specification without unnecessarily fixing a mechanism.

### Over-specification review

Identify normative statements that would force a new implementation to reproduce the current reference implementation.

If a mechanism is not intentionally part of the contract, rewrite the statement in terms of required semantics.

The specification is ready for implementation only when another competent agent can build a substantially different conforming realization without having to rediscover the subject's essential meaning.
