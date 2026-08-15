# Working on this repository

This repository is a generator. `tools/spec.py` and the guidance in `.spec/` and
`AGENTS.md` are the product; everything they produce is output.

## Layers

| Layer | Files | Changed by hand |
|---|---|---|
| Generator | `tools/spec.py` | yes |
| Schema | `.spec/schema/spec.schema.json` | yes |
| Guidance | `AGENTS.md`, `.spec/process.yaml`, `.spec/render.yaml` | yes |
| Self-description | `spec/` | yes — the template's own graph, and the only place a new key is demonstrated |
| Output | `SPEC.md`, `examples/**` | no — regenerate |

## Examples are output

`examples/` is what the generator plus the guidance produce when the documented
process is run against a subject. That includes the example's `spec/*.yaml`
graph, not only its rendered `SPEC.md`: the graph is the recovery's output, and
it is reproduced by re-running the recovery (`.claude/skills/benchmark-template`).

So a defect visible in an example is never fixed by editing the example. Only
changing the generator has value. Find the layer that produced the defect:

- **The document is assembled wrong** — sections, order, headings, labels,
  repetition → `tools/spec.py`, `.spec/render.yaml`.
- **A record has nowhere to put a needed fact** → schema, then the renderer, then
  a demonstration in `spec/`.
- **The graph could have expressed the better shape and the recovery did not
  choose it** → guidance. Chapter cuts, granularity, section membership, and how
  much to write in each section are guidance defects. "The knob already exists"
  is not a disposition.

Hand-patching an example makes the benchmark lie. The next recovery reproduces
the same defect, and the example stops being evidence about what the template
actually does.

## The deliverable is the rendered SPEC.md

Judge a change by reading the rendered document before and after, not by whether
the graph looks tidier. Never edit a `SPEC.md` directly — it is generated, and
`check` will fail.

New record keys are optional: a graph that omits one must still validate and
render, with its section simply absent.

## Commands

`PyYAML` is required (`pip install -r requirements.txt`).

```bash
make validate            # add DIR=examples/<name>/spec for an example
make render
make check               # fails when a rendered file is stale
```

Any rendering change makes every `SPEC.md` in the repository stale, including the
examples. Re-render all of them.
