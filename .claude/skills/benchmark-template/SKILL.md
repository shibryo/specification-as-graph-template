---
name: benchmark-template
description: >
  Improve the specification-as-graph template by benchmarking it. Clean-room
  recover a specification from an implementation, compare the rendered result
  against that subject's authoritative hand-written specification, classify each
  difference as a template defect or as example content, then fix the template.
  Use when asked to improve or validate the template, to run a benchmark
  recovery, or when a comparison against a hand-written specification has
  surfaced gaps.
---

# Benchmarking the template

This repository's product is the template: `tools/spec.py`, `.spec/`, `AGENTS.md`,
and the self-describing graph in `spec/`. Everything under `examples/` is a
diagnostic instrument, not a deliverable.

The benchmark is a controlled experiment. Recover a specification from an
implementation without looking at that subject's real specification, then read
the real one and see what the template failed to make you produce. What survives
that comparison is a template defect.

## Principles

Hold these before anything else. The first one is the one that gets lost.

- **The benchmark diagnoses; the template gets fixed.** A finding is not done
  when the example looks better. It is done when the template would have
  produced the better example on its own.
- **Same gap for any subject means template. Only this subject means content.**
  Ask: would a recovery of an unrelated subject hit this too?
- **An existing knob is not a defect.** If `chapters.yaml`, `parameters.yaml`, or
  an existing optional key could already express the difference, the finding is
  about how the example was written. Leave the template alone and say so.
- **Never fix the example to hide a template defect.** Editing the example first
  destroys the evidence and the next benchmark rediscovers the same gap.
- **A hand-written specification is not automatically right.** It can lag its own
  implementation. When it does, the recovery is correct and the disagreement is
  itself a finding worth recording.

## Phase 0 — Choose the pair and seal the answer key

You need two things about one subject:

1. an implementation you may read in full;
2. an authoritative implementation-facing specification of that same subject,
   written by its owners.

The second is the answer key. Before reading anything, **write down every path
that counts as an answer key** and state it to the user. At minimum:

- the specification file in the implementation's own repository;
- any prior recovery of the same subject in this repository's `examples/`;
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

Finish the phase properly: `validate` with **zero warnings**, then `render`. A
recovery that still warns is not evidence about the template; it is evidence
about the recoverer.

## Phase 2 — Compare

Now read the answer key. Build a difference ledger and keep it in the response;
it is the artifact the rest of the work is driven from.

| Difference | How the hand-written spec does it | Template today | Class | Goes to |
|---|---|---|---|---|

Classify every row:

| Class | Meaning | Goes to |
|---|---|---|
| `structure` | The hand-written spec organizes or renders something the template cannot express, or expresses differently | **Template** |
| `content` | The recovery missed a fact its sources contained | Example — but check whether a missing `required_view` let it happen |
| `deliberate` | The template's shape differs on purpose | Usually nothing. Ask whether a generated projection can serve both shapes |
| `key-is-stale` | The hand-written spec contradicts its own implementation | Nothing. Record the finding |

Two rows deserve extra suspicion:

- A `content` row that several unrelated recoveries would also miss is really a
  `structure` row wearing a disguise. Promote it.
- A `deliberate` row is the most common place to be lazy. State why the template's
  shape is better, or reclassify it.

## Phase 3 — Change the template

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
| `SPEC.md`, `examples/*/SPEC.md` | Any rendering change makes all of them stale |

Invariants for template changes:

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

## Phase 4 — Verify

Run the full matrix over the template and every example:

```bash
python tools/spec.py validate            # and: --dir examples/<name>/spec
python tools/spec.py render              # and: --dir examples/<name>/spec
python tools/spec.py check               # and: --dir examples/<name>/spec
```

`check` failing means a rendered file is stale. That is the usual symptom of
forgetting an example.

Then run the checks that `check` cannot do:

- **Negative checks.** When the change removes a phrase, `grep -c` it across every
  rendered file and confirm zero. Removals are the easiest thing to half-finish.
- **Absent-key checks.** Confirm a graph that omits a new optional key still
  renders, and that its section does not appear.
- **Untouched-section checks.** Diff a section the change should not affect. It
  should differ only by section numbering.
- **Self-description check.** Confirm the template's own `SPEC.md` demonstrates
  every new key.

## Closing the run

Report, in this order:

1. the difference ledger with each row's disposition;
2. what changed in the template, by layer;
3. rows deliberately left open, as named candidates for the next run.

Leaving rows open is normal. Leaving them unnamed is not.
