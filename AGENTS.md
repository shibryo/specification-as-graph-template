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
13. Recover the operator contract: every runtime-tunable setting that changes normative behavior becomes a parameter (`spec/parameters.yaml`) constraining the records it governs. The parameter's existence and semantics are normative; its name, format, and default stay implementation-defined unless the value itself is contractual. Give each parameter a `key` — a stable reference key used by the rendered document's configuration field list.
14. Give concepts at data boundaries a typed field list (`attributes`: name, type, requiredness, meaning). Field lists exist to carry per-field facts that prose property lists lose — requiredness, ordering direction, comparison rules — not storage layout.
15. Mark optional capability clusters as extensions (`conformance: extension` on chapters or records). Do not promote an extension to a core requirement, and do not drop it because it is optional.
16. Attach falsifiable verification clauses to interactions and invariants; the renderer assembles them into the test and validation matrix.
17. Give every implementation-defined area a documentation obligation (`document:`) when its selected mechanism affects observable behavior.
18. Use examples (`examples:` on interfaces and parameters) and reference algorithms (`algorithm:` on interactions) as informative aids for implementers. They are non-normative projections of the record they belong to and must not introduce semantics absent from it.
19. Run validation before rendering and regenerate `SPEC.md` after accepted changes.

## Plain style rule

Write specification prose the way implementation-facing specifications are written.

- Short declarative sentences. One idea per sentence.
- One fact per bullet. Split compound bullets into separate items.
- Never join two independent clauses with a comma. Use a period or a colon.
- Prefer subject-verb-object over nominalization.
- Target roughly 8-14 words per bullet where the fact allows.
- Shorten by splitting and simplifying, never by dropping a fact, a qualifier, or a normative word.
- Keep normative keywords and defined terms exactly.

Validation warns about overlong bullet items. Fix them by splitting, not by deleting content.

## Redundancy rule

Deliberate redundancy is a feature of good implementation-facing documents (cheat sheets, checklists, examples) and a maintenance hazard of hand-written ones. Here redundancy is generated: the configuration field list, the test and validation matrix, and the implementation checklist are projections of the same records as the body, so they cannot drift. Never hand-write a redundant summary into a record; add the projection to the renderer instead.

## Two implementers rule

The rendered SPEC.md serves two implementation styles at once. An implementer who transcribes needs a scan path: the configuration field list, concept field lists, the test and validation matrix, the implementation checklist, and informative examples and algorithms. An implementer who reconstructs needs an understanding path: problem, design intent, system model, and the chapters in reading order.

Every normative fact must be reachable through both paths. The renderer projects both from the same records, so they cannot disagree. When adding a record, ask which path each of its facts lands on; a fact reachable only through prose narrative fails the transcriber, and a fact reachable only through a table fails the reconstructor's understanding of why it holds.

## Provenance rule

Who writes a specification determines which mistakes it makes. An owner knows which mechanisms are deliberate and may fix them as contract; their risk is drift. A recoverer observes behavior and must guess what is contractual; their risk is freezing accidents.

- Declare the stance in the manifest: `stance: recovered` or `stance: owned`.
- Record what the recovery actually used in the evidence register (`spec/evidence.yaml`): each entry has a kind (`code`, `test`, `doc`, `behavior`, `statement`), a source location, and a note. Pin sources to a reference anchor (`reference.yaml`) so citations do not rot.
- Cite evidence from records via `evidence:` lists. Evidence is process metadata, not contract content; the renderer does not project it into `SPEC.md` at all.
- Record the basis of each invariant: `observed` (the reference implementation behaves this way), `stated` (a test, comment, or document asserts it), or `derived` (it is semantically necessary for a stated intent). The basis is a checkable claim, not a self-assessment: `stated` requires a cited test/doc/statement, `derived` requires a recorded intent, and in a recovered specification an invariant without citations is flagged.
- A mechanism whose only evidence is observed behavior is presumed implementation-defined. Promote it to normative only with a stated basis or a recorded semantic-necessity argument.
- In a recovered specification, constants and mechanism shapes default to implementation-defined. In an owned specification, the owners may fix the values they chose.

Validation checks basis against cited evidence, warns about invariants with no basis or no citations, and flags observed-only invariants for review.

## Sufficiency rule

Do not record what a competent implementer would necessarily reconstruct from the rest of the specification; record what they could not discover on their own.

Reconstructible (omit): the concrete value of a bounded constant, the shape of a growth curve whose required properties are stated, an obvious data structure, an encoding whose semantics are fixed.

Undiscoverable (record): that an operator parameter exists at all and what it governs, that a capability is an optional extension rather than core, that an implementation-defined choice must be documented, which side of a disagreement is authoritative, and how conformance is verified.

## Narrative integrity rule

`SPEC.md` MUST explain the subject as a coherent whole.

The renderer MUST NOT degrade into concatenating records in storage order. It must reconstruct at least these views when relevant:

- normative language;
- problem and design intent;
- system model;
- responsibility and ownership model;
- configuration specification (operator contract);
- end-to-end interactions;
- lifecycle and state transitions;
- interface semantics;
- invariants and constraints;
- failure and recovery model;
- implementation-defined freedom and documentation obligations;
- reference implementation relationship;
- test and validation matrix;
- implementation checklist and configuration field list (generated redundancy);
- conformance expectations, including the omissible extension surface.

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
