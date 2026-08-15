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
8. Treat inferred design intent as uncertain until supported by evidence. Write it at the grain of what it justifies, in the slot that already holds that grain — see the rationale rule. There is no design-intent record type.
9. Separate essential semantics from implementation-specific or reference-specific choices.
10. Attach normative statements to the model element they constrain.
11. Do not create an unstructured requirements list as the primary specification model.
12. Declare the subject's decomposition once as `layers:` in `spec/model.yaml`, in reading order, and group behavior records into chapters (`spec/chapters.yaml`) that expand those layers in that order. See the chapter order rule.
13. Recover the operator contract: every runtime-tunable setting that changes normative behavior becomes a parameter (`spec/parameters.yaml`) constraining the records it governs. The parameter's existence and semantics are normative; its name, format, and default stay implementation-defined unless the value itself is contractual. Give each parameter a `key` — a stable reference key used by the rendered document's configuration field list. State the reload contract once as `reload_default:`, and give a field its own `reload:` only where it departs from it. Have the chapter that specifies configuration behavior claim `parameters`, so a reader who opens it for "how does configuration take effect" finds the answer beside the fields.
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

## Rationale rule

Rationale has no record type and no section of its own. Write it where a reader
meets the thing it justifies:

| Grain | Slot |
|---|---|
| The whole subject | `context`, `problem`, `why_specification_exists` in `spec/intent.yaml` |
| One chapter | that chapter's `overview:` in `spec/chapters.yaml` |
| One record | `intent:` on the invariant, or a sentence in the record's own prose |

A list of design intents held apart from the records fails twice. It has to be
collected into a section nobody asked for, because a record that references
nothing and is referenced by nothing has no other placement. And it pre-announces
the invariants: a reader is told the same fact as rationale, then again one
section later as the statement they are actually checked against.

Before writing a reason anywhere, find the record it explains and check whether
that record already says it. Usually it does, or should.

## List label rule

A label above a list names what that list holds. It does not name the slot of
the record type the list came from.

Set `<field>_label` on the record wherever the type default would not tell a
reader anything: `requirements_label: Dispatch requirements`,
`prevents_label: Collisions this rules out`, `verification_label: Containment
checks`. The type-level default is a fallback for the case where the generic
word is genuinely the right one.

The measure is reuse across the whole rendered document. A hand-written
implementation specification reuses a label barely at all — each one names its
own section's content. A generated document that prints `Requirements:`
thirteen times has told a reader that the thirteen lists are interchangeable,
and by the third they are skimming. Reuse is a defect independent of whether
any single label is defensible.

Do not solve a repeated label by deleting the list or the lead-in. Name it.

## Placement rule

Only the analytical front of the document is fixed: Problem Statement, Goals
and Non-Goals, System Overview, Core Domain Model. Everything after it is
positioned by the subject's own decomposition, through `chapters.yaml`.

A chapter's `contains:` may claim, at most once each across the document:

- `lifecycle` — the state machine belongs to the component that owns it;
- `parameters` — the configuration field list belongs beside the behavior that
  resolves, validates, and reloads those fields.

An unclaimed lifecycle or field list falls back to a section of its own.

A record type that connects to nothing can only be dumped into a section that
collects all of it. When a new record type has no way to be placed, ask first
whether the facts belong on records that already exist. Adding a way to place it
is the second-best answer, and giving it a section of its own is not an answer.

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

Chapter structure is part of narrative integrity. When the subject spans more than one component, the graph MUST declare chapters (`spec/chapters.yaml`) that group interactions, interfaces, invariants, and failures — and, where it belongs to one component, the lifecycle — in reading order. The renderer projects chapters in declared order; records assigned to no chapter fall to an appendix and are reported by validation. Type-ordered projection is acceptable only for single-component subjects.

Identifiers used by `spec/` are internal graph identity. The rendered specification SHOULD prefer semantic names and prose unless an identifier itself is necessary for external traceability.

## Chapter order rule

Cut chapters by component, not by execution phase. Someone implementing one component should find it in one place, rather than assembled from a phase in one chapter and a boundary in another.

Then order the chapters so the document can be read straight through.

- **Declare the decomposition once.** `layers:` in `spec/model.yaml` states how the subject comes apart, in reading order, and renders as System Overview / Abstraction Levels. The body expands that list in that order. One layer may become more than one chapter — the state a component owns and the behavior that moves it are a common split — but each chapter belongs to one layer.
- **Explain nothing before what it rests on.** A chapter must be readable from the chapters before it. When a chapter uses a state name, an interface, or an invariant that another chapter defines, the defining chapter comes first.
- **Hoist shared vocabulary instead of reordering.** A noun two components both need belongs to the Core Domain Model, not to whichever chapter would otherwise have to come first.
- **Place assembly after its inputs.** A chapter that only combines what other chapters produce goes after the last chapter it takes an input from.
- **Sort extensions last.** Chapters marked `conformance: extension` follow every core chapter, whatever ordered the rest.
- **Record a coin-flip.** When the dependency test leaves two orders equally defensible, choose one and say why in a line. An order whose principle is stated can be argued with; an unstated one cannot.

Do not order chapters by distance from the user, by how the subject executes at runtime, or by what an implementer would build first. The first is not a property most subjects have. The second belongs to reference algorithms, the third to the test and validation matrix — both are already projected elsewhere in the document, and neither may reshuffle the body.

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
