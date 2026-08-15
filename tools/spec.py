#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict, deque
import argparse, sys, yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = ['manifest.yaml','intent.yaml','model.yaml','responsibilities.yaml','interactions.yaml','lifecycle.yaml','interfaces.yaml','invariants.yaml','failures.yaml','implementation-defined.yaml','reference.yaml']
OPTIONAL_FILES = ['chapters.yaml','parameters.yaml','evidence.yaml']
CONFORMANCE_LEVELS = {'core','extension'}
STANCES = {'recovered','owned'}
BASES = {'observed','stated','derived'}
EVIDENCE_KINDS = {'code','test','doc','behavior','statement'}

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

def first_sentence(v):
    s = ' '.join(str(v or '').strip().split())
    for sep in ['. ', '; ', ': ']:
        if sep in s: s = s.split(sep)[0]; break
    return sent(s)

def ext_suffix(x): return ' (Optional Extension)' if x.get('conformance') == 'extension' else ''

def refkey(p): return p.get('key') or p.get('name', p['id'])

def example_lines(x):
    L = []
    for ex in x.get('examples', []):
        if isinstance(ex, str): ex = {'body': ex}
        title = ex.get('title')
        L += [f"Example{': ' + title if title else ''}:", '', f"```{ex.get('lang','text')}"]
        L += str(ex.get('body', '')).rstrip().split('\n') + ['```', '']
    return L

def attribute_lines(c):
    attrs = c.get('attributes', [])
    if not attrs: return []
    L = ['Fields:', '']
    for a in attrs:
        typ = f" ({a['type']})" if a.get('type') else ''
        req = 'REQUIRED. ' if a.get('required') else ''
        L.append(f"- `{a.get('name')}`{typ} — {req}{sent(a.get('meaning'))}")
    return L + ['']

def ext_note(x):
    if x.get('conformance') != 'extension': return []
    return ['This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.','']

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
    for p in d['parameters.yaml'].get('parameters', []):
        pid = p.get('id')
        if not p.get('name') or not p.get('controls') or not p.get('semantics'): errors.append(f'{pid}: parameter needs name, controls, semantics')
        if not p.get('constrains'): errors.append(f'{pid}: parameter must constrain at least one record')
        for ref in p.get('constrains', []):
            if ref not in ids: errors.append(f'{pid}: constrains unknown reference {ref}')
    for item in all_records(d):
        c = item.get('conformance')
        if c is not None and c not in CONFORMANCE_LEVELS: errors.append(f"{item.get('id')}: invalid conformance value {c!r}")
        for a in item.get('attributes', []):
            if not isinstance(a, dict) or not a.get('name') or not a.get('meaning'): errors.append(f"{item.get('id')}: attribute needs name and meaning")
        for ex in item.get('examples', []):
            if isinstance(ex, dict) and not ex.get('body'): errors.append(f"{item.get('id')}: example needs body")
    for it in interactions:
        if not it.get('verification'): warnings.append(f"{it.get('id')}: interaction has no verification; it is absent from the verification matrix")
    for inv in invs:
        if not inv.get('verification'): warnings.append(f"{inv.get('id')}: invariant has no verification; it is absent from the verification matrix")
    stance = d['manifest.yaml'].get('specification', {}).get('stance')
    if stance is not None and stance not in STANCES: errors.append(f'manifest: invalid stance {stance!r}')
    evidence = [e for e in d['evidence.yaml'].get('evidence', []) if isinstance(e, dict)]
    kind_by_evidence = {}
    for e in evidence:
        eid = e.get('id')
        if not e.get('kind') or not e.get('source'): errors.append(f'{eid}: evidence needs kind and source')
        elif e.get('kind') not in EVIDENCE_KINDS: errors.append(f"{eid}: invalid evidence kind {e.get('kind')!r}")
        kind_by_evidence[eid] = e.get('kind')
    for item in all_records(d):
        for ref in item.get('evidence', []):
            if ref not in kind_by_evidence: errors.append(f"{item.get('id')}: unknown evidence reference {ref}")
    for inv in invs:
        basis = inv.get('basis')
        refs = inv.get('evidence', [])
        cited_kinds = {kind_by_evidence.get(r) for r in refs}
        if basis is None: warnings.append(f"{inv.get('id')}: invariant has no basis; record whether it is observed, stated, or derived")
        elif basis not in BASES: errors.append(f"{inv.get('id')}: invalid basis {basis!r}")
        elif basis == 'observed': warnings.append(f"{inv.get('id')}: basis is observed only; confirm the mechanism is contractual or move it to implementation-defined")
        elif basis == 'stated' and not (cited_kinds & {'test','doc','statement'}): errors.append(f"{inv.get('id')}: basis is stated but no cited evidence is a test, doc, or statement")
        elif basis == 'derived' and not inv.get('intent'): errors.append(f"{inv.get('id')}: basis is derived but the invariant records no intent (the semantic-necessity argument)")
        if stance == 'recovered' and not refs: warnings.append(f"{inv.get('id')}: recovered specification; cite evidence for this invariant in spec/evidence.yaml")
    STYLE_FIELDS = ['properties','semantics','prevents','required_behavior','fixed_semantics','document','input_semantics','output_semantics','failure_semantics','implementation_defined','preconditions','postconditions','owns','must_not_own','normative','implications','tradeoffs']
    STYLE_MAX_WORDS = 28
    for item in all_records(d):
        for field in STYLE_FIELDS:
            for entry in item.get(field, []):
                if isinstance(entry, str) and len(entry.split()) > STYLE_MAX_WORDS:
                    warnings.append(f"{item.get('id')}: style: {field} item has {len(entry.split())} words; split it into one fact per bullet")
        for req in item.get('requirements', []):
            stmt = req.get('statement','') if isinstance(req, dict) else ''
            if len(str(stmt).split()) > STYLE_MAX_WORDS:
                warnings.append(f"{item.get('id')}: style: requirement statement has {len(str(stmt).split())} words; simplify it")
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
    L = [f"{h} {it.get('name',it['id'])}{ext_suffix(it)}",'',sent(it.get('purpose')),'']+ext_note(it)
    ps=[label(x,idx) for x in it.get('participants',[])]
    if ps: L += ['Participants: '+', '.join(f'**{x}**' for x in ps)+'.','']
    if it.get('trigger'): L+=[f"Trigger: {sent(it['trigger'])}",'']
    if it.get('preconditions'): L+=['Preconditions:','']+bullets(it['preconditions'])+['']
    if it.get('sequence'):
        L+=['Sequence:','']
        for n,s in enumerate(it['sequence'],1): L += [f"{n}. **{label(s.get('actor',''),idx)}** {sent(s.get('action'))}"]
        L+=['']
    if it.get('postconditions'): L+=['Postconditions:','']+bullets(it['postconditions'])+['']
    for req in it.get('requirements',[]): L += [f"- **{str(req.get('level','must')).upper().replace('_',' ')}** — {sent(req.get('statement'))}"]
    if it.get('requirements'): L+=['']
    if it.get('invariants'): L+=['Constrained by '+', '.join(f"**{label(x,idx)}**" for x in it['invariants'])+'.','']
    if it.get('failures'): L+=['Failures: '+', '.join(f"**{label(x,idx)}**" for x in it['failures'])+'.','']
    if it.get('algorithm'): L+=['Reference algorithm (non-normative):','','```text']+str(it['algorithm']).rstrip().split('\n')+['```','']
    if it.get('verification'): L+=['Validation checks:','']+bullets(it['verification'])+['']
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
    L = [f"{h} {x.get('name',x['id'])}{ext_suffix(x)}",'',sent(x.get('purpose')),'']+ext_note(x)
    for title,key in [('Input semantics','input_semantics'),('Output semantics','output_semantics'),('Failure semantics','failure_semantics')]:
        if x.get(key): L += [f'{title}:','']+bullets(x[key])+['']
    if x.get('implementation_defined'): L += ['Implementation-defined mechanisms:','']+bullets(x['implementation_defined'])+['']
    L += example_lines(x)
    if x.get('verification'): L+=['**Verification**','']+bullets(x['verification'])+['']
    return L

def parameter_lines(p, idx):
    L = [f"- `{refkey(p)}` — {sent(p.get('controls'))}"]
    for s in p.get('semantics', []): L.append(f"  - {sent(s)}")
    if p.get('reload'): L.append(f"  - Reload: {sent(p['reload'])}")
    if p.get('constrains'): L.append('  - Used by ' + ', '.join(f"**{label(x,idx)}**" for x in p['constrains']) + '.')
    for ln in example_lines(p): L.append(f'  {ln}' if ln else '')
    return L

def checklist_lines(d, params, sec_no=None):
    def split(xs): return [x for x in xs if x.get('conformance')!='extension'], [x for x in xs if x.get('conformance')=='extension']
    def names(xs): return ', '.join(f"**{x.get('name',x['id'])}**" for x in xs)
    ic,ie = split(d['interactions.yaml'].get('interactions',[]))
    xc,xe = split(d['interfaces.yaml'].get('interfaces',[]))
    vc,ve = split(d['invariants.yaml'].get('invariants',[]))
    fc,fe = split(d['failures.yaml'].get('failures',[]))
    pc,pe = split(params)
    if not (ic or xc or vc or fc or pc): return []
    core_head = f"### {sec_no}.1 Core" if sec_no else '### Core'
    ext_head = f"### {sec_no}.2 Optional extensions (normative in full when implemented)" if sec_no else '### Optional extensions (normative in full when implemented)'
    L = ['Generated from the specification graph. Intentionally redundant with the body.','',core_head,'']
    if ic: L.append(f'- Interactions: {names(ic)}.')
    if d['lifecycle.yaml'].get('states'): L.append('- Lifecycle: implement every state and transition of the lifecycle.')
    if xc: L.append(f'- Interfaces: {names(xc)}.')
    if vc: L.append(f'- Invariants: {names(vc)}.')
    if fc: L.append(f'- Failure semantics: {names(fc)}.')
    if pc: L.append('- Configuration fields: '+', '.join(f'`{refkey(p)}`' for p in pc)+'.')
    L.append('- Documentation: record the selected behavior for every implementation-defined area.')
    L.append('')
    ext = ie+xe+ve+fe
    if ext or pe:
        L += [ext_head,'']
        L += [f"- **{x.get('name',x['id'])}**" for x in ext]
        L += [f"- `{refkey(p)}`" for p in pe]
        L.append('')
    return L

def invariant_lines(x, h):
    L = [f"{h} {x.get('name',x['id'])}",'',sent(x.get('statement')),'']
    if x.get('intent'): L+=[sent(x['intent']),'']
    if x.get('prevents'): L+=['This prevents:','']+bullets(x['prevents'])+['']
    if x.get('verification'): L+=['Validation checks:','']+bullets(x['verification'])+['']
    return L

def failure_lines(x, idx, h):
    L = [f"{h} {x.get('name',x['id'])}{ext_suffix(x)}",'',sent(x.get('meaning')),'']+ext_note(x)
    if x.get('occurs_during'): L += ['Occurs during '+', '.join(f"**{label(r,idx)}**" for r in x['occurs_during'])+'.','']
    L += [f"Retryable: {x.get('retryable','unspecified')}.",'']
    if x.get('required_behavior'): L+=['Requirements:','']+bullets(x['required_behavior'])+['']
    if x.get('recovery'): L+=[f"Recovery: {sent(x['recovery'])}",'']
    if x.get('verification'): L+=['Validation checks:','']+bullets(x['verification'])+['']
    return L

def stance_lines(m):
    stance = m.get('stance')
    if stance == 'recovered':
        return ['Provenance: recovered from an existing implementation. Where the evidence was behavior alone, mechanisms default to implementation-defined.','']
    if stance == 'owned':
        return ["Provenance: authored by the subject's owners. Fixed mechanisms are deliberate contract.",'']
    return []

def reading_guide_lines(d, params):
    scan, deep = [], []
    if params: scan.append('The Configuration Specification lists every operator-settable field.')
    if any(c.get('attributes') for c in d['model.yaml'].get('concepts', [])): scan.append('Concept field lists give the data contract.')
    if any(x.get('verification') for x in d['interactions.yaml'].get('interactions', []) + d['invariants.yaml'].get('invariants', [])): scan.append('The Test and Validation Matrix lists the checks an implementation must pass.')
    scan.append('The Implementation Checklist is the definition of done.')
    if any(x.get('examples') for x in d['interfaces.yaml'].get('interfaces', []) + d['parameters.yaml'].get('parameters', [])) or any(x.get('algorithm') for x in d['interactions.yaml'].get('interactions', [])):
        scan.append('Examples and reference algorithms show one concrete shape. They are informative, not normative.')
    deep += ['The Problem Statement and Design Intent say why the subject exists.','The System Overview and Core Domain Model define the participants and who owns each decision.']
    deep.append('The chapters walk through behavior end to end.' if d['chapters.yaml'].get('chapters') else 'The interaction, lifecycle, and interface sections walk through behavior end to end.')
    deep.append('Invariants and failures state what must survive your design choices.')
    L = ['## How to Read This Specification','','This specification serves two implementation styles.','','To implement by transcription, use the scan path:','']
    L += bullets(scan) + ['','To implement by reconstruction, read in order:',''] + bullets(deep)
    L += ['','Both paths are projections of the same records. They cannot disagree.','']
    return L

def normative_language_lines(m_all):
    nl = m_all.get('normative_language')
    if not nl: return []
    order = ['must','must_not','should','should_not','may','implementation_defined','unspecified']
    keys = [k for k in order if k in nl] + [k for k in nl if k not in order]
    L = ['## Normative Language','','The key words below carry the stated meaning wherever they appear in this specification.','']
    for k in keys:
        disp = k.upper().replace('_',' ') if k in ('must','must_not','should','should_not','may') else k.replace('_','-').capitalize()
        L.append(f'- **{disp}** — {sent(nl[k])}')
    return L + ['']

def verification_matrix_lines(d, idx, sec_no=None):
    chapters = d['chapters.yaml'].get('chapters', [])
    behavior = []
    for key, coll in [('interactions.yaml','interactions'),('interfaces.yaml','interfaces'),('invariants.yaml','invariants'),('failures.yaml','failures')]:
        behavior += [x for x in d[key].get(coll, []) if isinstance(x, dict) and x.get('verification')]
    if not behavior: return []
    by_id = {x['id']: x for x in behavior}
    def rows(items):
        out = []
        for x in items:
            for v in x.get('verification', []): out.append(f"- **{x.get('name', x['id'])}** — {sent(v)}")
        return out
    L = ['Checks assembled from the verification clauses of this specification. A conforming implementation should be able to demonstrate each of them. Checks under an optional extension apply only when that extension is implemented.','']
    def head(i, title):
        return f"### {sec_no}.{i} {title}" if sec_no else f"### {i}. {title}"
    if chapters:
        emitted = set(); i = 0
        for ch in chapters:
            items = [by_id[ref] for ref in ch.get('contains', []) if ref in by_id]
            if not items: continue
            emitted.update(x['id'] for x in items); i += 1
            L += [head(i, f"{ch.get('name', ch.get('id'))}{ext_suffix(ch)}"), ''] + rows(items) + ['']
        rest = [x for x in behavior if x['id'] not in emitted]
        if rest: i += 1; L += [head(i, 'General'), ''] + rows(rest) + ['']
    else:
        L += rows(behavior) + ['']
    return L

def render(d):
    idx,_=make_index(d); m=d['manifest.yaml']['specification']; intent=d['intent.yaml']; model=d['model.yaml']; rs=d['responsibilities.yaml'].get('responsibilities',[]); its=d['interactions.yaml'].get('interactions',[]); life=d['lifecycle.yaml']
    ifaces=d['interfaces.yaml'].get('interfaces',[]); invs=d['invariants.yaml'].get('invariants',[]); fails=d['failures.yaml'].get('failures',[]); chapters=d['chapters.yaml'].get('chapters',[])
    params=d['parameters.yaml'].get('parameters',[])
    L=[f"# {m['name']} Specification",'',"> GENERATED FROM `spec/`. DO NOT EDIT DIRECTLY.",'',f"Status: {m.get('status','draft')}  ",f"Version: {m.get('version','0.1.0')}",'']
    L+=stance_lines(m)
    L+=['---','']
    L+=normative_language_lines(d['manifest.yaml'])
    L+=reading_guide_lines(d,params)
    sec=[0]
    def h2(title):
        sec[0]+=1
        return [f"## {sec[0]}. {title}",'']
    L+=h2('Problem Statement')+[sent(intent.get('context')),'',sent(intent.get('problem')),'']
    if intent.get('why_specification_exists'): L+=[f"### {sec[0]}.1 Why This Specification Exists",'',sent(intent['why_specification_exists']),'']
    L+=h2('Goals and Non-Goals')+[f"### {sec[0]}.1 Goals",'']+bullets(intent.get('goals',[]))+['',f"### {sec[0]}.2 Non-Goals",'']+bullets(intent.get('non_goals',[]))+['']
    cs=model.get('concepts',[])
    L+=h2('System Overview')
    if model.get('overview'): L+=[sent(model['overview']),'']
    sub=0
    if rs:
        sub+=1
        L+=[f"### {sec[0]}.{sub} Main Components",'','One line per component, then its ownership. Generated from the same records as the rest of this document.','']
        L+=[f"- **{r.get('name',r['id'])}**{ext_suffix(r)} — {first_sentence(r.get('purpose'))}" for r in rs]+['']
        for r in rs:
            L += [f"#### {r.get('name',r['id'])}{ext_suffix(r)}",'',sent(r.get('purpose')),'']
            if r.get('owns'): L+=['It owns:','']+bullets(r['owns'])+['']
            if r.get('must_not_own'): L+=['It does not own:','']+bullets(r['must_not_own'])+['']
            if r.get('normative'): L+=['Requirements:','']+bullets(r['normative'])+['']
    if model.get('external_dependencies'):
        sub+=1
        L+=[f"### {sec[0]}.{sub} External Dependencies",'','A conforming deployment requires this environment.','']+bullets(model['external_dependencies'])+['']
    L+=h2('Core Domain Model')
    sub=0
    if cs:
        sub+=1
        L+=[f"### {sec[0]}.{sub} Entities",'','One line per entity, then its full definition. Generated from the same records as the rest of this document.','']
        L+=[f"- **{c.get('name',c['id'])}**{ext_suffix(c)} — {first_sentence(c.get('meaning'))}" for c in cs]+['']
        for c in cs: L += [f"#### {c.get('name',c['id'])}{ext_suffix(c)}",'',sent(c.get('meaning')),'']+attribute_lines(c)+bullets(c.get('properties',[]))+['']
    if model.get('relationships'):
        sub+=1
        L+=[f"### {sec[0]}.{sub} Relationships",'']
        for rel in model['relationships']: L += [f"**{label(rel['subject'],idx)}** {rel.get('relation','relates to').replace('_',' ')} **{label(rel['object'],idx)}**. {sent(rel.get('meaning'))}",'']
    if intent.get('design_intents'):
        L+=h2('Design Intent')
        for x in intent['design_intents']:
            L+=[f"### {x.get('name','Intent')}",'',sent(x.get('intent')),'']
            if x.get('why_it_matters'): L+=[sent(x['why_it_matters']),'']
            if x.get('implications'): L+=['Implications:','']+bullets(x['implications'])+['']
            if x.get('tradeoffs'): L+=['Notes:','']+bullets(x['tradeoffs'])+['']
    if params:
        L+=h2('Configuration Specification')+['Each field below must exist and be operator-settable. Keys are reference names used by this document, not required spellings. Concrete names, formats, and defaults are implementation-defined unless fixed elsewhere. The stated semantics are normative. One entry per field; sub-bullets give its semantics, reload behavior, and the behaviors it governs.','']
        pc=[p for p in params if p.get('conformance')!='extension']
        pe=[p for p in params if p.get('conformance')=='extension']
        if pc:
            L+=[f"### {sec[0]}.1 Core Fields",'']
            for p in pc: L+=parameter_lines(p,idx)
            L+=['']
        if pe:
            L+=[f"### {sec[0]}.2 Extension Fields",'','These fields exist only when their extension is implemented.','']
            for p in pe: L+=parameter_lines(p,idx)
            L+=['']
    iids={x['id'] for x in its}; vids={x['id'] for x in invs}; fids={x['id'] for x in fails}; xids={x['id'] for x in ifaces}
    if chapters:
        assigned=set(); life_claimed=False
        for ch in chapters:
            L+=h2(f"{ch.get('name',ch.get('id'))}{ext_suffix(ch)}")
            if ch.get('overview'): L+=[sent(ch['overview']),'']
            L+=ext_note(ch)
            for ref in ch.get('contains',[]):
                if ref=='lifecycle':
                    life_claimed=True
                    L+=['### Lifecycle and State','']+lifecycle_lines(life,idx,'####')
                elif ref in iids: L+=interaction_lines(idx[ref],idx,'###'); assigned.add(ref)
                elif ref in vids: L+=invariant_lines(idx[ref],'###'); assigned.add(ref)
                elif ref in fids: L+=failure_lines(idx[ref],idx,'###'); assigned.add(ref)
                elif ref in xids: L+=interface_lines(idx[ref],'###'); assigned.add(ref)
        if not life_claimed: L+=h2('Lifecycle and State')+lifecycle_lines(life,idx,'###')
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
        L+=h2('Core Interactions')
        for it in its: L+=interaction_lines(it,idx,'###')
        L+=h2('Lifecycle and State')+lifecycle_lines(life,idx,'###')
        L+=h2('Interfaces and Interactions')
        for x in ifaces: L+=interface_lines(x,'###')
        L+=h2('Invariants and Constraints')
        for x in invs: L+=invariant_lines(x,'###')
        L+=h2('Failure and Recovery Semantics')
        for x in fails: L+=failure_lines(x,idx,'###')
    areas=d['implementation-defined.yaml'].get('areas',[])
    if areas: L+=h2('Implementation-Defined Areas')
    for x in areas:
        L += [f"### {x.get('name','Area')}",'',sent(x.get('freedom')),'']
        if x.get('fixed_semantics'): L+=['Fixed semantics:','']+bullets(x['fixed_semantics'])+['']
        if x.get('document'): L+=['A conforming implementation must document:','']+bullets(x['document'])+['']
    ref=d['reference.yaml'].get('reference_implementation',{})
    L+=h2('Reference Implementation')+[sent(ref.get('summary','No reference implementation is defined.')),'']
    if ref.get('normative') is False: L+=['The reference implementation is **not normative**; it is one realization of this specification.','']
    vm=verification_matrix_lines(d,idx,sec_no=sec[0]+1)
    if vm: L+=h2('Test and Validation Matrix')+vm
    cl=checklist_lines(d,params,sec_no=sec[0]+1)
    if cl: L+=h2('Implementation Checklist (Definition of Done)')+cl
    conf=['satisfies applicable normative semantics','preserves conceptual relationships and responsibility boundaries','implements the defined interactions and lifecycle semantics','preserves invariants and defined failure behavior','may choose different mechanisms where implementation freedom is declared','documents its selected behavior for every implementation-defined area','does not treat reference-specific choices as additional requirements']
    if params: conf.insert(4,'exposes every field in the configuration specification with its stated semantics')
    if any(x.get('conformance')=='extension' for x in all_records(d)): conf.append('may omit optional extensions entirely; every implemented extension is normative in full')
    L+=h2('Conformance')+[sent(d['manifest.yaml'].get('implementation_instruction')),'','A conforming implementation:','']+bullets(conf)+['']
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
