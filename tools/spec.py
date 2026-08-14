#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict, deque
import argparse, sys, yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = ['manifest.yaml','intent.yaml','model.yaml','responsibilities.yaml','interactions.yaml','lifecycle.yaml','interfaces.yaml','invariants.yaml','failures.yaml','implementation-defined.yaml','reference.yaml']
OPTIONAL_FILES = ['chapters.yaml']

def load(spec_dir):
    docs = {}
    for f in FILES:
        p = spec_dir / f
        if not p.exists(): raise SystemExit(f'missing required file: {p}')
        docs[f] = yaml.safe_load(p.read_text()) or {}
    for f in OPTIONAL_FILES:
        p = spec_dir / f
        docs[f] = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
    return docs

def all_records(docs):
    for doc in docs.values():
        for value in doc.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get('id'), str): yield item

def make_index(docs):
    idx, errors = {}, []
    for item in all_records(docs):
        rid = item['id']
        if rid in idx: errors.append(f'duplicate id: {rid}')
        idx[rid] = item
    return idx, errors

def label(ref, idx):
    item = idx.get(ref, {})
    return str(item.get('name') or item.get('title') or ref)

def sent(v):
    s = ' '.join(str(v or '').strip().split())
    return s if not s or s[-1] in '.!?:;' else s + '.'

def bullets(xs): return [f'- {sent(x)}' for x in xs]

def validate(d):
    idx, errors = make_index(d); warnings = []; ids = set(idx)
    model = d['model.yaml']; concepts = model.get('concepts', [])
    cids = {x.get('id') for x in concepts if isinstance(x, dict)}
    rs = d['responsibilities.yaml'].get('responsibilities', [])
    rids = {x.get('id') for x in rs if isinstance(x, dict)}
    interactions = d['interactions.yaml'].get('interactions', [])
    invs = d['invariants.yaml'].get('invariants', [])
    fails = d['failures.yaml'].get('failures', [])
    used_r, used_c, used_i, used_f = set(), set(), set(), set()
    for rel in model.get('relationships', []):
        if rel.get('subject') not in ids or rel.get('object') not in ids: errors.append('model relationship has unknown reference')
    for it in interactions:
        iid = it.get('id'); ps = it.get('participants', [])
        if not it.get('purpose') or not it.get('trigger') or not it.get('sequence'): errors.append(f'{iid}: interaction needs purpose, trigger, sequence')
        for p in ps:
            if p not in ids: errors.append(f'{iid}: unknown participant {p}')
            if p in rids: used_r.add(p)
            if p in cids: used_c.add(p)
        if not any(p in rids for p in ps): errors.append(f'{iid}: interaction needs a responsibility')
        if not any(p in cids for p in ps): errors.append(f'{iid}: interaction needs a concept')
        for step in it.get('sequence', []):
            if step.get('actor') not in ps: errors.append(f'{iid}: step actor must be a participant')
        for x in it.get('invariants', []): used_i.add(x)
        for x in it.get('failures', []): used_f.add(x)
    life = d['lifecycle.yaml']; states = {x.get('id') for x in life.get('states', []) if isinstance(x, dict)}; initial = life.get('initial_state')
    if states and initial not in states: errors.append('lifecycle requires a valid initial_state')
    edges = defaultdict(list)
    for tr in life.get('transitions', []):
        a,b = tr.get('from'),tr.get('to')
        if a not in states or b not in states or not tr.get('trigger'): errors.append('lifecycle transition is incomplete')
        elif a in states and b in states: edges[a].append(b)
    if initial in states:
        seen,q={initial},deque([initial])
        while q:
            cur=q.popleft()
            for nxt in edges[cur]:
                if nxt not in seen: seen.add(nxt);q.append(nxt)
        for x in states-seen: errors.append(f'unreachable lifecycle state: {x}')
    for inv in invs:
        if not inv.get('statement'): errors.append(f"{inv.get('id')}: invariant needs statement")
        if interactions and inv.get('id') not in used_i: errors.append(f"{inv.get('id')}: invariant is disconnected")
    for f in fails:
        if not f.get('occurs_during') or not f.get('required_behavior'): errors.append(f"{f.get('id')}: failure is incomplete")
        if interactions and f.get('id') not in used_f: errors.append(f"{f.get('id')}: failure is disconnected")
    if not concepts: errors.append('whole-system: at least one concept is required')
    if len(concepts)>1 and not model.get('relationships'): errors.append('whole-system: concepts need relationships')
    if not rs: errors.append('whole-system: at least one responsibility is required')
    if not interactions: errors.append('whole-system: at least one interaction is required')
    if not invs: errors.append('whole-system: at least one invariant is required')
    for x in rids-used_r: errors.append(f'whole-system: disconnected responsibility {x}')
    if len(cids)>1:
        for x in cids-used_c: errors.append(f'whole-system: disconnected concept {x}')
    chapters = d['chapters.yaml'].get('chapters', [])
    xids = {x.get('id') for x in d['interfaces.yaml'].get('interfaces', []) if isinstance(x, dict)}
    iids = {x.get('id') for x in interactions if isinstance(x, dict)}
    vids = {x.get('id') for x in invs if isinstance(x, dict)}
    fids = {x.get('id') for x in fails if isinstance(x, dict)}
    chapterable = iids | vids | fids | xids
    assigned, life_owner = {}, None
    for ch in chapters:
        cid = ch.get('id')
        if not ch.get('name'): errors.append(f'{cid}: chapter needs name')
        contains = ch.get('contains', [])
        if not contains: errors.append(f'{cid}: chapter needs contains')
        for ref in contains:
            if ref == 'lifecycle':
                if life_owner: errors.append(f'{cid}: lifecycle already belongs to chapter {life_owner}')
                else: life_owner = cid
            elif ref not in chapterable: errors.append(f'{cid}: contains unknown or non-chapterable reference {ref}')
            elif ref in assigned: errors.append(f'{ref}: record belongs to chapters {assigned[ref]} and {cid}')
            else: assigned[ref] = cid
    if chapters:
        for x in sorted(chapterable - set(assigned)): warnings.append(f'{x}: not assigned to any chapter; it renders in the appendix')
    return errors, warnings

def interaction_lines(it, idx, h):
    L = [f"{h} {it.get('name',it['id'])}",'',sent(it.get('purpose')),'']
    ps=[label(x,idx) for x in it.get('participants',[])]
    if ps: L += ['Participants: '+', '.join(f'**{x}**' for x in ps)+'.','']
    if it.get('trigger'): L+=['The interaction begins when '+sent(it['trigger']).lower(),'']
    if it.get('preconditions'): L+=['Before it begins:','']+bullets(it['preconditions'])+['']
    if it.get('sequence'):
        L+=['The interaction proceeds as follows:','']
        for n,s in enumerate(it['sequence'],1): L += [f"{n}. **{label(s.get('actor',''),idx)}** {sent(s.get('action'))}"]
        L+=['']
    if it.get('postconditions'): L+=['On completion:','']+bullets(it['postconditions'])+['']
    for req in it.get('requirements',[]): L += [f"- **{str(req.get('level','must')).upper().replace('_',' ')}** — {sent(req.get('statement'))}"]
    if it.get('requirements'): L+=['']
    if it.get('invariants'): L+=['Constrained by '+', '.join(f"**{label(x,idx)}**" for x in it['invariants'])+'.','']
    if it.get('failures'): L+=['Defined failures: '+', '.join(f"**{label(x,idx)}**" for x in it['failures'])+'.','']
    return L

def lifecycle_lines(life, idx, h):
    L=[]
    if life.get('initial_state'): L += [f"The lifecycle begins in **{label(life['initial_state'],idx)}**.",'']
    terminal=set(life.get('terminal_states',[]))
    for s in life.get('states',[]): L += [f"- **{s.get('name',s['id'])}** — {sent(s.get('meaning'))}{' This is terminal.' if s.get('id') in terminal else ''}"]
    L+=['',f'{h} Transitions','']
    for t in life.get('transitions',[]): L += [f"- **{label(t['from'],idx)}** → **{label(t['to'],idx)}** when {sent(t.get('trigger')).lower()}"]
    L+=['']
    if life.get('normative'): L+=[f'{h} Lifecycle Constraints','']+bullets(life['normative'])+['']
    return L

def interface_lines(x, h):
    L = [f"{h} {x.get('name',x['id'])}",'',sent(x.get('purpose')),'']
    for title,key in [('Input semantics','input_semantics'),('Output semantics','output_semantics'),('Failure semantics','failure_semantics')]:
        if x.get(key): L += [f'**{title}**','']+bullets(x[key])+['']
    if x.get('implementation_defined'): L += ['Implementation-defined mechanisms:','']+bullets(x['implementation_defined'])+['']
    return L

def invariant_lines(x, h):
    L = [f"{h} {x.get('name',x['id'])}",'',sent(x.get('statement')),'']
    if x.get('intent'): L+=['**Intent**','',sent(x['intent']),'']
    if x.get('prevents'): L+=['**This prevents**','']+bullets(x['prevents'])+['']
    if x.get('verification'): L+=['**Verification**','']+bullets(x['verification'])+['']
    return L

def failure_lines(x, idx, h):
    L = [f"{h} {x.get('name',x['id'])}",'',sent(x.get('meaning')),'']
    if x.get('occurs_during'): L += ['Occurs during '+', '.join(f"**{label(r,idx)}**" for r in x['occurs_during'])+'.','']
    L += [f"Retryability is **{x.get('retryable','unspecified')}**.",'']
    if x.get('required_behavior'): L+=['**Required behavior**','']+bullets(x['required_behavior'])+['']
    if x.get('recovery'): L+=['**Recovery**','',sent(x['recovery']),'']
    return L

def render(d):
    idx,_=make_index(d); m=d['manifest.yaml']['specification']; intent=d['intent.yaml']; model=d['model.yaml']; rs=d['responsibilities.yaml'].get('responsibilities',[]); its=d['interactions.yaml'].get('interactions',[]); life=d['lifecycle.yaml']
    ifaces=d['interfaces.yaml'].get('interfaces',[]); invs=d['invariants.yaml'].get('invariants',[]); fails=d['failures.yaml'].get('failures',[]); chapters=d['chapters.yaml'].get('chapters',[])
    L=[f"# {m['name']} Specification",'',"> GENERATED FROM `spec/`. DO NOT EDIT DIRECTLY.",'',f"Status: {m.get('status','draft')}  ",f"Version: {m.get('version','0.1.0')}",'','---','']
    L+=['## Problem Statement','',sent(intent.get('context')),'',sent(intent.get('problem')),'']
    if intent.get('why_specification_exists'): L+=['### Why This Specification Exists','',sent(intent['why_specification_exists']),'']
    L+=['## Goals and Non-Goals','','### Goals','']+bullets(intent.get('goals',[]))+['','### Non-Goals','']+bullets(intent.get('non_goals',[]))+['','## Design Intent','']
    for x in intent.get('design_intents',[]):
        L+=[f"### {x.get('name','Intent')}",'',sent(x.get('intent')),'']
        if x.get('why_it_matters'): L+=['**Why it matters**','',sent(x['why_it_matters']),'']
        if x.get('implications'): L+=['**Implications**','']+bullets(x['implications'])+['']
        if x.get('tradeoffs'): L+=['**Trade-offs**','']+bullets(x['tradeoffs'])+['']
    L+=['## System Model','','### Core Concepts','']
    for c in model.get('concepts',[]): L += [f"#### {c.get('name',c['id'])}",'',sent(c.get('meaning')),'']+bullets(c.get('properties',[]))+['']
    if model.get('relationships'):
        L+=['### Concept Relationships','']
        for r in model['relationships']: L += [f"**{label(r['subject'],idx)}** {r.get('relation','relates to').replace('_',' ')} **{label(r['object'],idx)}**. {sent(r.get('meaning'))}",'']
    L+=['### Responsibilities and Ownership','']
    for r in rs:
        L += [f"#### {r.get('name',r['id'])}",'',sent(r.get('purpose')),'']
        if r.get('owns'): L+=['It owns:','']+bullets(r['owns'])+['']
        if r.get('must_not_own'): L+=['It does not own:','']+bullets(r['must_not_own'])+['']
        if r.get('normative'): L+=['Normative ownership semantics:','']+bullets(r['normative'])+['']
    iids={x['id'] for x in its}; vids={x['id'] for x in invs}; fids={x['id'] for x in fails}; xids={x['id'] for x in ifaces}
    if chapters:
        assigned=set(); life_claimed=False
        for n,ch in enumerate(chapters,1):
            L+=[f"## {n}. {ch.get('name',ch.get('id'))}",'']
            if ch.get('overview'): L+=[sent(ch['overview']),'']
            for ref in ch.get('contains',[]):
                if ref=='lifecycle':
                    life_claimed=True
                    L+=['### Lifecycle and State','']+lifecycle_lines(life,idx,'####')
                elif ref in iids: L+=interaction_lines(idx[ref],idx,'###'); assigned.add(ref)
                elif ref in vids: L+=invariant_lines(idx[ref],'###'); assigned.add(ref)
                elif ref in fids: L+=failure_lines(idx[ref],idx,'###'); assigned.add(ref)
                elif ref in xids: L+=interface_lines(idx[ref],'###'); assigned.add(ref)
        if not life_claimed: L+=['## Lifecycle and State','']+lifecycle_lines(life,idx,'###')
        rest=[x for x in its if x['id'] not in assigned]+[x for x in ifaces if x['id'] not in assigned]+[x for x in invs if x['id'] not in assigned]+[x for x in fails if x['id'] not in assigned]
        if rest:
            L+=['## Appendix A. Records Outside Chapters','','The following records are normative but are not assigned to any chapter.','']
            for x in its:
                if x['id'] not in assigned: L+=interaction_lines(x,idx,'###')
            for x in ifaces:
                if x['id'] not in assigned: L+=interface_lines(x,'###')
            for x in invs:
                if x['id'] not in assigned: L+=invariant_lines(x,'###')
            for x in fails:
                if x['id'] not in assigned: L+=failure_lines(x,idx,'###')
    else:
        L+=['## Core Interactions','']
        for it in its: L+=interaction_lines(it,idx,'###')
        L+=['## Lifecycle and State','']+lifecycle_lines(life,idx,'###')
        L+=['## Interfaces and Interactions','']
        for x in ifaces: L+=interface_lines(x,'###')
        L+=['## Invariants and Constraints','']
        for x in invs: L+=invariant_lines(x,'###')
        L+=['## Failure and Recovery Semantics','']
        for x in fails: L+=failure_lines(x,idx,'###')
    L+=['## Implementation-Defined Areas','']
    for x in d['implementation-defined.yaml'].get('areas',[]):
        L += [f"### {x.get('name','Area')}",'',sent(x.get('freedom')),'']
        if x.get('fixed_semantics'): L+=['Fixed semantics:','']+bullets(x['fixed_semantics'])+['']
    ref=d['reference.yaml'].get('reference_implementation',{})
    L+=['## Reference Implementation','',sent(ref.get('summary','No reference implementation is defined.')),'']
    if ref.get('normative') is False: L+=['The reference implementation is **not normative**; it is one realization of this specification.','']
    L+=['## Conformance','',sent(d['manifest.yaml'].get('implementation_instruction')),'','A conforming implementation:','']+bullets(['satisfies applicable normative semantics','preserves conceptual relationships and responsibility boundaries','implements the defined interactions and lifecycle semantics','preserves invariants and defined failure behavior','may choose different mechanisms where implementation freedom is declared','does not treat reference-specific choices as additional requirements'])+['']
    return '\n'.join(L).rstrip()+'\n'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('command', choices=['validate','render','check'])
    p.add_argument('--dir', default=None, help='specification graph directory (default: <repo>/spec)')
    args=p.parse_args()
    spec_dir=Path(args.dir).resolve() if args.dir else ROOT/'spec'
    out=spec_dir.parent/'SPEC.md'
    docs=load(spec_dir); errors,warnings=validate(docs)
    for w in warnings: print('WARNING:',w,file=sys.stderr)
    if errors:
        for e in errors: print('ERROR:',e,file=sys.stderr)
        return 1
    if args.command=='validate': print('specification graph is valid'); return 0
    text=render(docs)
    if args.command=='render': out.write_text(text); print(f'rendered {out}'); return 0
    if not out.exists() or out.read_text()!=text: print(f'ERROR: {out} is stale; run render',file=sys.stderr); return 1
    print(f'{out} is up to date'); return 0

if __name__=='__main__': raise SystemExit(main())
