---
name: benchmark-template
description: >
  Improve this repository by benchmarking it. Clean-room recover a specification
  from an implementation, compare the rendered SPEC.md against that subject's
  authoritative hand-written specification, classify each difference by where it
  has to be fixed, take a human reading of the document before changing anything,
  then fix and re-read. Use when asked to improve or validate the template, to run
  a benchmark recovery, or when a comparison against a hand-written specification
  has surfaced gaps.
---

# Benchmarking the template

What this repository produces is a `SPEC.md`: a specification precise enough for
an agent to implement from, that still explains the subject as a whole. Every
other file exists to make that document good. `spec/` is the source of truth, the
renderer is the projection, and `SPEC.md` is never edited by hand.

The benchmark is a controlled experiment on that document. Recover a
specification from an implementation without looking at that subject's real
specification, render it, then read the real one and compare the two documents.
Whatever the hand-written one does better is a defect in ours.

## Principles

Hold these before anything else. Each one has already been got wrong.

- **Judge by the rendered document.** A change is good when `SPEC.md` reads
  better, not when the graph looks tidier or the tooling gets cleverer. Read the
  rendered output before and after.
- **A person is the only instrument for document quality.** Connectivity and
  freshness are machine-checkable; whether the document is tiring, monotone, or
  hollow is not. Phase 3 is a gate, not a courtesy.
- **Never hand-edit `SPEC.md`.** If the document is wrong, the graph, the
  renderer, or the guidance is wrong. Fix that and re-render.
- **Fix the cause, not the symptom.** A finding fixed only in one example leaves
  every future `SPEC.md` carrying it. Find the layer that would have prevented
  it, fix there, then bring the example along.
- **A knob nobody reaches for is a guidance defect.** If the graph could already
  express the better shape but the recovery did not produce it, the renderer is
  fine and `AGENTS.md` / `.spec/process.yaml` are not. That is still a repository
  fix, not a shrug.
- **A hand-written specification is not automatically right.** It can lag its own
  implementation. When it does, the recovery is correct and the disagreement is
  itself a finding worth recording.

## Phase 0 — Choose the pair and seal the answer key

You need two things about one subject:

1. an implementation you may read in full — the input;
2. an authoritative implementation-facing specification of that same subject,
   written by its owners — the exemplar, and therefore the answer key.

### Default pair

Unless the user names another subject, use:

| Role | Source |
|---|---|
| Input | `openai/symphony`, the `elixir/` subtree |
| Exemplar | `openai/symphony/SPEC.md` at the repository root |

A local clone is usually at `~/ghq/github.com/openai/symphony`. Check `git log -1`
and pin that revision in the recovery's `reference.yaml`; evidence citations are
only as good as their anchor.

Everything else in that repository is readable input, including `elixir/README.md`,
`elixir/AGENTS.md`, `elixir/docs/`, `elixir/WORKFLOW.md`, the test suite, and the
root `README.md`. Only the root `SPEC.md` is sealed.

### Sealing

Before reading anything, **write down every path that counts as an answer key**
and state it to the user. At minimum:

- the specification file in the implementation's own repository;
- any prior recovery of the same subject under `examples/`;
- any rendered `SPEC.md` derived from either.

If a prior recovery of this subject exists at the path you will write to, delete
it from the working tree before starting. Git history keeps it, and the deletion
is what makes the run clean-room. Confirm the deletion with the user first when
it is tracked work.

## Phase 1 — Clean-room recovery

Sources you may read:

- implementation code;
- tests — test names are `stated` evidence, and are often the only place a rule
  is written down;
- implementation-side documentation: README, contributor guides, design notes,
  configuration samples.

Sources you may not read: everything sealed in Phase 0.

Follow `.spec/process.yaml` and `AGENTS.md` for the recovery itself. Do not
restate that process here — if it is wrong, fix those files, which is the whole
point of this skill.

Finish the phase properly: `validate` with **zero warnings**, then `render`, then
**read the rendered document end to end**. A recovery you have not read is not
evidence about anything. Your reading prepares findings; it does not settle them.
Phase 3 settles them.

## Phase 2 — Compare

Now read the answer key. Compare document against document, not graph against
prose. Build a difference ledger and keep it in the response; the rest of the
work is driven from it.

| Difference | How the hand-written spec does it | Ours today | Class | Fix in |
|---|---|---|---|---|

Classify every row by **where the fix has to land**:

| Class | Meaning | Fix in |
|---|---|---|
| `renderer` | The graph holds the facts but the document presents them worse, or cannot present them at all | `tools/spec.py`, `.spec/render.yaml` |
| `schema` | The graph has nowhere to put something the document needs | record shape, validator, `.spec/schema/`, plus a demonstration in `spec/` |
| `guidance` | The graph could have expressed it, but the process did not lead the author there | `AGENTS.md`, `.spec/process.yaml` — then re-cut the example |
| `content` | The recovery missed a fact its sources contained | the example's graph — and ask what would have caught it |
| `deliberate` | Ours differs on purpose and is defensible | nothing, but say why in the ledger |
| `key-is-stale` | The hand-written spec contradicts its own implementation | nothing. Record the finding |

Rows that get misclassified:

- `content` that several unrelated recoveries would also miss is `guidance` in
  disguise. Promote it.
- "The knob already exists" is not a disposition. If the knob existed and the
  document still came out worse, the row is `guidance`.
- `deliberate` is where laziness hides. Justify it against the rendered document
  or reclassify it.

## Phase 3 — Human sensory evaluation (gate)

**Stop here. Do not carry the ledger into Phase 4 on your own authority.**

Everything the machinery can check, it has already checked. `validate` proves the
graph connects. `check` proves nothing is stale. Neither can tell you the document
is tiring to read, that every record lands with the same rhythm, that a heading
promised something it did not deliver, or that a section reads like output rather
than like a specification a person would keep maintaining. Those are perceptual
judgements, and the only instrument for them is a person reading the document.

Your own reading does not substitute. An agent evaluating prose it just produced
is the weakest evaluator available, and fluent-but-flat is exactly the failure it
cannot feel.

### What to hand over

- the rendered document, by path, with its size and roughly how long it takes to read;
- what changed since they last saw it, if anything;
- the difference ledger with your proposed disposition per row;
- the rows you are least sure about, named, with why.

### What to ask

Ask for perception, not permission. "Does this look OK?" returns a yes and
destroys the signal. Ask what only a reader can answer:

- Where did you start skimming, and what made you start?
- Where did you have to read something twice?
- Does the tempo vary, or does every record land the same way?
- Which section felt like filler written to fill a slot?
- Read the exemplar's equivalent section. Which of the two reads like a document
  a person would keep maintaining?
- Which heading made you expect something you did not then get?
- If you had to cut a fifth of it, what goes first?

Do not argue a perception away. If a section reads as flat to a reader, it is
flat. The open question is which layer made it flat.

### What to do with the answers

Each perception becomes a ledger row and is classified like any other finding.
Where they usually land:

- "reads flat", "no variation", "nothing to look at" → `renderer`, often with
  `schema` behind it: the graph has no slot for the shape the content wants —
  a table, a figure, a worked example;
- "every section says the same kind of thing" → `guidance`: the records were
  authored uniformly because nothing told the author to vary them;
- "this heading is odd", "nobody writes this" → `renderer`, invented vocabulary;
- "this part was a slog and I skipped it" → decide honestly between `renderer`
  (projected badly) and `content` (genuinely too much said).

A perception you cannot land in a layer is still a finding. Record it unclassified
rather than dropping it.

## Phase 4 — Fix

One change ripples. Walk these layers in order every time, and say which ones the
change does not touch rather than skipping them silently.

| Layer | When it changes |
|---|---|
| `tools/spec.py` | Validator rules, rendering, projections |
| `.spec/schema/spec.schema.json` | The shape of a record changes |
| `.spec/render.yaml` | Sections, strategies, vocabulary, generated redundancy |
| `.spec/process.yaml` | Required views, classification and normalization rules |
| `AGENTS.md` | Rules an authoring agent must follow |
| `spec/` | The template's self-description — a new key nobody demonstrates is invisible |
| `examples/*/spec/` | The worked example is a published deliverable, not scratch |
| `SPEC.md`, `examples/*/SPEC.md` | Any rendering change makes all of them stale |
| `README.md` | It describes the worked example's shape; re-cutting chapters dates it |

Invariants for repository changes:

- **New record keys are optional.** A graph without them must still validate and
  render, with the corresponding section simply absent.
- **Redundant sections are projections.** Never let a record carry a hand-written
  summary of other records. Add the projection to the renderer instead.
- **No invented editorial labels.** Rendered headings must come from the lexicon
  of hand-written implementation-facing specifications. `.spec/render.yaml`
  carries this rule; the renderer has violated it before.
- **The renderer adds no semantics.** If a fact is not in the graph, rendering
  must not introduce it.
- **Do not drop a fact to match a shape.** When the hand-written spec's section is
  lighter than ours, relocate the surplus content, do not delete it.

## Phase 5 — Verify

Run the full matrix over the template and every example:

```bash
python tools/spec.py validate            # and: --dir examples/<name>/spec
python tools/spec.py render              # and: --dir examples/<name>/spec
python tools/spec.py check               # and: --dir examples/<name>/spec
```

`check` failing means a rendered file is stale. That is the usual symptom of
forgetting an example.

Then run the checks that `check` cannot do:

- **Read the diff of the rendered documents.** This is the actual acceptance test.
  Everything below is a guard against ways of fooling yourself about it.
- **Negative checks.** When the change removes a phrase, `grep -c` it across every
  rendered file and confirm zero. Removals are the easiest thing to half-finish.
- **Absent-key checks.** Confirm a graph that omits a new optional key still
  renders, and that its section does not appear.
- **Untouched-section checks.** Diff a section the change should not affect. It
  should differ only by section numbering.
- **Self-description check.** Confirm the template's own `SPEC.md` demonstrates
  every new key.

### Second sensory gate

Then hand the changed document back. This pass is lighter than Phase 3 — give
them the rendered diff and the sections it touched, and ask whether the document
reads better, worse, or merely different.

A fix that satisfies every row of the ledger and leaves the document worse to
read is not finished. Ledger rows are a proxy; the reading is the thing they were
a proxy for.

## Closing the run

Report, in this order:

1. the difference ledger with each row's disposition, including the rows that came
   from the reader rather than from the comparison;
2. what changed, by layer;
3. rows deliberately left open, as named candidates for the next run.

Leaving rows open is normal. Leaving them unnamed is not.
