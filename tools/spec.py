#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict, deque
import argparse, re, sys, yaml

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

def lab(x, field, default):
    """The lead-in printed above a record's list.

    A label names what the list holds, not which slot of the record type it came
    from. `<field>_label` lets the record say so; the type-level default is only
    the fallback, and a document where every default survives is a document whose
    labels carry no information.
    """
    v = x.get(field + '_label')
    return f"{' '.join(str(v).split()).rstrip(':')}:" if v else default

# Cross-references are written as a name plus a placeholder, and the section
# number is substituted once the whole document is numbered. A reference to a
# record that never got a number loses its parenthetical instead of dangling.
SECMAP = {}
SEC_TOKEN = re.compile(r' \(Section \{\{sec:([^}]+)\}\}\)')

def secref(rid): return f' (Section {{{{sec:{rid}}}}})'

def resolve_sections(text):
    return SEC_TOKEN.sub(lambda m: f' (Section {SECMAP[m.group(1)]})' if m.group(1) in SECMAP else '', text)

def named(rid, idx): return f"**{label(rid, idx)}**{secref(rid)}"

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

def subsections(no, parts, level='###'):
    """Render the structural subsections of section `no` at `level`.

    `parts` is a list of (title, build), where build(h) returns the body and h is
    the heading level its own children must use. A section left with a single
    subsection folds into its parent: a heading that numbers one child divides
    nothing. Folding is for structural splits only — never for a list of records,
    where the heading carries a record's name and dropping it would lose a fact.
    """
    if not parts: return []
    if len(parts) == 1: return parts[0][1](level, no)
    L = []
    for i, (title, build) in enumerate(parts, 1):
        n = f"{no}.{i}"
        L += [f"{level} {n} {title}", ''] + build('#' + level, n)
    return L

def numbered(records, no, level, render):
    """Number a list of records as `no`.1, `no`.2, ... at `level`."""
    L = []
    for n, x in enumerate(records, 1):
        if isinstance(x.get('id'), str): SECMAP[x['id']] = f"{no}.{n}"
        L += render(x, f"{level} {no}.{n}")
    return L

def layer_lines(layers):
    L = []
    for n, ly in enumerate(layers, 1):
        scope = f" ({str(ly['scope']).strip().rstrip('.')})" if ly.get('scope') else ''
        L.append(f"{n}. **{ly.get('name', ly.get('id'))}**{scope}")
        L += [f"   - {sent(c)}" for c in ly.get('contents', [])]
        L.append('')
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
    if d['intent.yaml'].get('design_intents'):
        errors.append('intent.yaml: design_intents is not a record type. Rationale is written at the grain of what it justifies: a whole-subject boundary belongs in the problem statement, a chapter-level reason in that chapter overview, and a record-level reason in that record intent')
    for n, ly in enumerate(model.get('layers', []), 1):
        if not isinstance(ly, dict) or not isinstance(ly.get('id'), str): errors.append(f'model layer {n}: layer needs an id')
        elif not ly.get('name'): errors.append(f"{ly['id']}: layer needs a name")
        elif not ly.get('contents'): errors.append(f"{ly['id']}: layer needs contents")
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
    STYLE_FIELDS = ['properties','semantics','prevents','required_behavior','fixed_semantics','document','input_semantics','output_semantics','failure_semantics','implementation_defined','preconditions','postconditions','owns','must_not_own','normative','implications','tradeoffs','contents']
    STYLE_MAX_WORDS = 28
    for item in all_records(d):
        for field in STYLE_FIELDS:
            for entry in item.get(field, []):
                if not isinstance(entry, str):
                    errors.append(f"{item.get('id')}: {field} item is {type(entry).__name__}, not text; an unquoted colon makes YAML read the bullet as a mapping")
                elif len(entry.split()) > STYLE_MAX_WORDS:
                    warnings.append(f"{item.get('id')}: style: {field} item has {len(entry.split())} words; split it into one fact per bullet")
        for req in item.get('requirements', []):
            stmt = req.get('statement','') if isinstance(req, dict) else ''
            if len(str(stmt).split()) > STYLE_MAX_WORDS:
                warnings.append(f"{item.get('id')}: style: requirement statement has {len(str(stmt).split())} words; simplify it")
        for k, v in item.items():
            if not (isinstance(k, str) and k.endswith('_label')): continue
            if not isinstance(v, str) or not v.strip(): errors.append(f"{item.get('id')}: {k} must be a non-empty label")
            elif not item.get(k[:-len('_label')]): errors.append(f"{item.get('id')}: {k} names a list the record does not have")
            elif len(v.split()) > 6: warnings.append(f"{item.get('id')}: style: {k} has {len(v.split())} words; a label names what the list holds in a few words")
    if not d['manifest.yaml'].get('normative_language'): errors.append('manifest: normative_language is required; the document uses MUST and SHOULD, so their meaning must be defined')
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
    assigned, life_owner, param_owner = {}, None, None
    layer_order = {ly['id']: n for n, ly in enumerate(model.get('layers', [])) if isinstance(ly, dict) and isinstance(ly.get('id'), str)}
    reached, ext_chapter = -1, None
    for ch in chapters:
        cid = ch.get('id')
        if not ch.get('name'): errors.append(f'{cid}: chapter needs name')
        contains = ch.get('contains', [])
        if not contains: errors.append(f'{cid}: chapter needs contains')
        lay = ch.get('layer')
        if lay is None:
            if layer_order: warnings.append(f'{cid}: chapter names no layer, so its position is not checked against the declared decomposition')
        elif lay not in layer_order: errors.append(f'{cid}: unknown layer {lay}')
        elif layer_order[lay] < reached: errors.append(f'{cid}: chapter order contradicts the declared layers; {lay} is declared before the layer an earlier chapter already reached')
        else: reached = layer_order[lay]
        if ch.get('conformance') == 'extension': ext_chapter = cid
        elif ext_chapter: errors.append(f'{cid}: core chapter follows extension chapter {ext_chapter}; extension chapters sort last')
        for ref in contains:
            if ref == 'lifecycle':
                if life_owner: errors.append(f'{cid}: lifecycle already belongs to chapter {life_owner}')
                else: life_owner = cid
            elif ref == 'parameters':
                if param_owner: errors.append(f'{cid}: parameters already belong to chapter {param_owner}')
                elif not d['parameters.yaml'].get('parameters'): errors.append(f'{cid}: contains parameters but the graph declares none')
                else: param_owner = cid
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
    if it.get('preconditions'): L+=[lab(it,'preconditions','Preconditions:'),'']+bullets(it['preconditions'])+['']
    if it.get('sequence'):
        L+=[lab(it,'sequence','Sequence:'),'']
        for n,s in enumerate(it['sequence'],1): L += [f"{n}. **{label(s.get('actor',''),idx)}** {sent(s.get('action'))}"]
        L+=['']
    if it.get('postconditions'): L+=[lab(it,'postconditions','Postconditions:'),'']+bullets(it['postconditions'])+['']
    if it.get('requirements'):
        L+=[lab(it,'requirements','Requirements:'),'']
        L+=[f"- **{str(req.get('level','must')).upper().replace('_',' ')}** — {sent(req.get('statement'))}" for req in it['requirements']]+['']
    if it.get('invariants'): L+=['Constrained by '+', '.join(named(x,idx) for x in it['invariants'])+'.','']
    if it.get('failures'): L+=['Failures: '+', '.join(named(x,idx) for x in it['failures'])+'.','']
    if it.get('algorithm'): L+=['Reference algorithm (non-normative):','','```text']+str(it['algorithm']).rstrip().split('\n')+['```','']
    if it.get('verification'): L+=[lab(it,'verification','Validation checks:'),'']+bullets(it['verification'])+['']
    return L

def lifecycle_lines(life, idx, no, level):
    L=[]
    if life.get('initial_state'): L += [f"The lifecycle begins in **{label(life['initial_state'],idx)}**.",'']
    terminal=set(life.get('terminal_states',[]))
    for s in life.get('states',[]): L += [f"- **{s.get('name',s['id'])}** — {sent(s.get('meaning'))}{' This is terminal.' if s.get('id') in terminal else ''}"]
    L+=['']
    def transitions(h, n):
        return [f"- **{label(t['from'],idx)}** → **{label(t['to'],idx)}** when {sent(t.get('trigger')).lower()}" for t in life.get('transitions',[])]+['']
    parts=[('Transitions', transitions)]
    if life.get('normative'): parts.append(('Lifecycle Constraints', lambda h,n: bullets(life['normative'])+['']))
    return L + subsections(no, parts, level)

def interface_lines(x, h):
    L = [f"{h} {x.get('name',x['id'])}{ext_suffix(x)}",'',sent(x.get('purpose')),'']+ext_note(x)
    for title,key in [('Input semantics','input_semantics'),('Output semantics','output_semantics'),('Failure semantics','failure_semantics')]:
        if x.get(key): L += [lab(x,key,f'{title}:'),'']+bullets(x[key])+['']
    if x.get('implementation_defined'): L += [lab(x,'implementation_defined','Implementation-defined mechanisms:'),'']+bullets(x['implementation_defined'])+['']
    L += example_lines(x)
    if x.get('verification'): L+=[lab(x,'verification','Validation checks:'),'']+bullets(x['verification'])+['']
    return L

def parameter_lines(p, idx):
    L = [f"- `{refkey(p)}` — {sent(p.get('controls'))}"]
    for s in p.get('semantics', []): L.append(f"  - {sent(s)}")
    if p.get('reload'): L.append(f"  - Reload: {sent(p['reload'])}")
    if p.get('constrains'): L.append('  - Used by ' + ', '.join(named(x,idx) for x in p['constrains']) + '.')
    for ln in example_lines(p): L.append(f'  {ln}' if ln else '')
    return L

def configuration_lines(params, reload_default, idx, no, level):
    """The operator contract: every field, its semantics, and what it governs.

    Rendered wherever the graph puts it — inside the chapter that claims
    `parameters`, or as a section of its own when no chapter claims it.
    """
    L = ['Each field below must exist and be operator-settable. Keys are reference names used by this document, not required spellings. Concrete names, formats, and defaults are implementation-defined unless fixed elsewhere. The stated semantics are normative. One entry per field; sub-bullets give its semantics and the behaviors it governs.','']
    if reload_default:
        L += [f"Reload: {sent(reload_default)} A field whose reload behavior differs states its own.",'']
    pc=[p for p in params if p.get('conformance')!='extension']
    pe=[p for p in params if p.get('conformance')=='extension']
    def field_lines(ps, lead=None):
        def build(h, n):
            out=list(lead) if lead else []
            for p in ps: out+=parameter_lines(p,idx)
            return out+['']
        return build
    parts=[]
    if pc: parts.append(('Core Fields', field_lines(pc)))
    if pe: parts.append(('Extension Fields', field_lines(pe, ['These fields exist only when their extension is implemented.',''])))
    return L + subsections(no, parts, level)

def checklist_lines(d, params, sec_no=None):
    def split(xs): return [x for x in xs if x.get('conformance')!='extension'], [x for x in xs if x.get('conformance')=='extension']
    def names(xs): return ', '.join(f"**{x.get('name',x['id'])}**" for x in xs)
    ic,ie = split(d['interactions.yaml'].get('interactions',[]))
    xc,xe = split(d['interfaces.yaml'].get('interfaces',[]))
    vc,ve = split(d['invariants.yaml'].get('invariants',[]))
    fc,fe = split(d['failures.yaml'].get('failures',[]))
    pc,pe = split(params)
    if not (ic or xc or vc or fc or pc): return []
    def core(h, no):
        out = []
        if ic: out.append(f'- Interactions: {names(ic)}.')
        if d['lifecycle.yaml'].get('states'): out.append('- Lifecycle: implement every state and transition of the lifecycle.')
        if xc: out.append(f'- Interfaces: {names(xc)}.')
        if vc: out.append(f'- Invariants: {names(vc)}.')
        if fc: out.append(f'- Failure semantics: {names(fc)}.')
        if pc: out.append('- Configuration fields: '+', '.join(f'`{refkey(p)}`' for p in pc)+'.')
        out.append('- Documentation: record the selected behavior for every implementation-defined area.')
        return out + ['']
    ext = ie+xe+ve+fe
    def extensions(h, no):
        return [f"- **{x.get('name',x['id'])}**" for x in ext] + [f"- `{refkey(p)}`" for p in pe] + ['']
    parts = [('Core', core)]
    if ext or pe: parts.append(('Optional extensions (normative in full when implemented)', extensions))
    return ['Generated from the specification graph. Intentionally redundant with the body.',''] + subsections(sec_no, parts)

def invariant_lines(x, h):
    L = [f"{h} {x.get('name',x['id'])}",'',sent(x.get('statement')),'']
    if x.get('intent'): L+=[sent(x['intent']),'']
    if x.get('prevents'): L+=[lab(x,'prevents','This prevents:'),'']+bullets(x['prevents'])+['']
    if x.get('verification'): L+=[lab(x,'verification','Validation checks:'),'']+bullets(x['verification'])+['']
    return L

def failure_lines(x, idx, h):
    L = [f"{h} {x.get('name',x['id'])}{ext_suffix(x)}",'',sent(x.get('meaning')),'']+ext_note(x)
    if x.get('occurs_during'): L += ['Occurs during '+', '.join(named(r,idx) for r in x['occurs_during'])+'.','']
    L += [f"Retryable: {x.get('retryable','unspecified')}.",'']
    if x.get('required_behavior'): L+=[lab(x,'required_behavior','Required behavior:'),'']+bullets(x['required_behavior'])+['']
    if x.get('recovery'): L+=[f"Recovery: {sent(x['recovery'])}",'']
    if x.get('verification'): L+=[lab(x,'verification','Validation checks:'),'']+bullets(x['verification'])+['']
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
    if params: scan.append('The configuration field list gives every operator-settable field.')
    if any(c.get('attributes') for c in d['model.yaml'].get('concepts', [])): scan.append('Concept field lists give the data contract.')
    if any(x.get('verification') for x in d['interactions.yaml'].get('interactions', []) + d['invariants.yaml'].get('invariants', [])): scan.append('The Test and Validation Matrix lists the checks an implementation must pass.')
    scan.append('The Implementation Checklist is the definition of done.')
    if any(x.get('examples') for x in d['interfaces.yaml'].get('interfaces', []) + d['parameters.yaml'].get('parameters', [])) or any(x.get('algorithm') for x in d['interactions.yaml'].get('interactions', [])):
        scan.append('Examples and reference algorithms show one concrete shape. They are informative, not normative.')
    deep += ['The Problem Statement says why the subject exists and which boundaries it holds to.','The System Overview and Core Domain Model define the participants and who owns each decision.']
    deep.append('The chapters walk through behavior end to end.' if d['chapters.yaml'].get('chapters') else 'The interaction, lifecycle, and interface sections walk through behavior end to end.')
    deep.append('Invariants and failures state what must survive your design choices.')
    L = ['## How to Read This Specification','','This specification serves two implementation styles.','','To implement by transcription, use the scan path:','']
    L += bullets(scan) + ['','To implement by reconstruction, read in order:',''] + bullets(deep)
    L += ['','Both paths are projections of the same records. They cannot disagree.','']
    return L

def normative_language_lines(m_all):
    nl = m_all.get('normative_language', {})
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
    if chapters:
        parts, emitted = [], set()
        for ch in chapters:
            items = [by_id[ref] for ref in ch.get('contains', []) if ref in by_id]
            if not items: continue
            emitted.update(x['id'] for x in items)
            parts.append((f"{ch.get('name', ch.get('id'))}{ext_suffix(ch)}", (lambda xs: lambda h,no: rows(xs) + [''])(items)))
        rest = [x for x in behavior if x['id'] not in emitted]
        if rest: parts.append(('General', lambda h,no: rows(rest) + ['']))
        L += subsections(sec_no, parts)
    else:
        L += rows(behavior) + ['']
    return L

def render(d):
    idx,_=make_index(d); m=d['manifest.yaml']['specification']; intent=d['intent.yaml']; model=d['model.yaml']; rs=d['responsibilities.yaml'].get('responsibilities',[]); its=d['interactions.yaml'].get('interactions',[]); life=d['lifecycle.yaml']
    ifaces=d['interfaces.yaml'].get('interfaces',[]); invs=d['invariants.yaml'].get('invariants',[]); fails=d['failures.yaml'].get('failures',[]); chapters=d['chapters.yaml'].get('chapters',[])
    params=d['parameters.yaml'].get('parameters',[]); reload_default=d['parameters.yaml'].get('reload_default')
    SECMAP.clear()
    claimed={ref for ch in chapters for ref in ch.get('contains',[])}
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
    if intent.get('why_specification_exists'): L+=[sent(intent['why_specification_exists']),'']
    goal_parts=[]
    if intent.get('goals'): goal_parts.append(('Goals', lambda h,no: bullets(intent['goals'])+['']))
    if intent.get('non_goals'): goal_parts.append(('Non-Goals', lambda h,no: bullets(intent['non_goals'])+['']))
    if goal_parts:
        L+=h2(' and '.join(t for t,_ in goal_parts))
        L+=subsections(sec[0], goal_parts)
    cs=model.get('concepts',[])
    def one_component(r, h):
        who=r.get('name',r['id'])
        out=[f"{h} {who}{ext_suffix(r)}",'',sent(r.get('purpose')),'']
        if r.get('owns'): out+=[lab(r,'owns',f'{who} owns:'),'']+bullets(r['owns'])+['']
        if r.get('must_not_own'): out+=[lab(r,'must_not_own',f'{who} does not own:'),'']+bullets(r['must_not_own'])+['']
        if r.get('normative'): out+=[lab(r,'normative','Ownership requirements:'),'']+bullets(r['normative'])+['']
        return out
    def one_entity(c, h):
        return [f"{h} {c.get('name',c['id'])}{ext_suffix(c)}",'',sent(c.get('meaning')),'']+attribute_lines(c)+bullets(c.get('properties',[]))+['']
    def component_lines(h, no):
        return (['One line per component, then its ownership. Generated from the same records as the rest of this document.','']
                +[f"- **{r.get('name',r['id'])}**{ext_suffix(r)} — {first_sentence(r.get('purpose'))}" for r in rs]+['']
                +numbered(rs, no, h, one_component))
    def entity_lines(h, no):
        return (['One line per entity, then its full definition. Generated from the same records as the rest of this document.','']
                +[f"- **{c.get('name',c['id'])}**{ext_suffix(c)} — {first_sentence(c.get('meaning'))}" for c in cs]+['']
                +numbered(cs, no, h, one_entity))
    def relationship_lines(h, no):
        out=[]
        for rel in model['relationships']: out += [f"**{label(rel['subject'],idx)}** {rel.get('relation','relates to').replace('_',' ')} **{label(rel['object'],idx)}**. {sent(rel.get('meaning'))}",'']
        return out
    L+=h2('System Overview')
    if model.get('overview'): L+=[sent(model['overview']),'']
    parts=[('Main Components', component_lines)]
    if model.get('layers'): parts.append(('Abstraction Levels', lambda h,no: ['The subject is easiest to port when kept in these layers.','']+layer_lines(model['layers'])))
    if model.get('external_dependencies'): parts.append(('External Dependencies', lambda h,no: ['A conforming deployment requires this environment.','']+bullets(model['external_dependencies'])+['']))
    L+=subsections(sec[0], parts)
    L+=h2('Core Domain Model')
    parts=[('Entities', entity_lines)]
    if model.get('relationships'): parts.append(('Relationships', relationship_lines))
    L+=subsections(sec[0], parts)
    if params and 'parameters' not in claimed:
        L+=h2('Configuration Specification')+configuration_lines(params,reload_default,idx,sec[0],'###')
    iids={x['id'] for x in its}; vids={x['id'] for x in invs}; fids={x['id'] for x in fails}; xids={x['id'] for x in ifaces}
    if chapters:
        assigned=set(); life_claimed=False
        for ch in chapters:
            L+=h2(f"{ch.get('name',ch.get('id'))}{ext_suffix(ch)}")
            if ch.get('overview'): L+=[sent(ch['overview']),'']
            L+=ext_note(ch)
            sub=0
            for ref in ch.get('contains',[]):
                sub+=1; no=f"{sec[0]}.{sub}"; h=f"### {no}"
                if ref=='lifecycle':
                    life_claimed=True
                    L+=[f'{h} Lifecycle and State','']+lifecycle_lines(life,idx,no,'####')
                elif ref=='parameters':
                    L+=[f'{h} Configuration Fields','']+configuration_lines(params,reload_default,idx,no,'####')
                elif ref in iids: SECMAP[ref]=no; L+=interaction_lines(idx[ref],idx,h); assigned.add(ref)
                elif ref in vids: SECMAP[ref]=no; L+=invariant_lines(idx[ref],h); assigned.add(ref)
                elif ref in fids: SECMAP[ref]=no; L+=failure_lines(idx[ref],idx,h); assigned.add(ref)
                elif ref in xids: SECMAP[ref]=no; L+=interface_lines(idx[ref],h); assigned.add(ref)
                else: sub-=1
        if not life_claimed:
            L+=h2('Lifecycle and State')+lifecycle_lines(life,idx,sec[0],'###')
        rest=[x for x in its if x['id'] not in assigned]+[x for x in ifaces if x['id'] not in assigned]+[x for x in invs if x['id'] not in assigned]+[x for x in fails if x['id'] not in assigned]
        if rest:
            L+=['## Appendix A. Records Outside Chapters','','The following records are normative but are not assigned to any chapter.','']
            for n,x in enumerate(rest,1):
                h=f"### A.{n}"; SECMAP[x['id']]=f"A.{n}"
                if x['id'] in iids: L+=interaction_lines(x,idx,h)
                elif x['id'] in xids: L+=interface_lines(x,h)
                elif x['id'] in vids: L+=invariant_lines(x,h)
                else: L+=failure_lines(x,idx,h)
    else:
        L+=h2('Core Interactions')+numbered(its,sec[0],'###',lambda x,h: interaction_lines(x,idx,h))
        L+=h2('Lifecycle and State')+lifecycle_lines(life,idx,sec[0],'###')
        L+=h2('Interfaces and Interactions')+numbered(ifaces,sec[0],'###',lambda x,h: interface_lines(x,h))
        L+=h2('Invariants and Constraints')+numbered(invs,sec[0],'###',lambda x,h: invariant_lines(x,h))
        L+=h2('Failure and Recovery Semantics')+numbered(fails,sec[0],'###',lambda x,h: failure_lines(x,idx,h))
    areas=d['implementation-defined.yaml'].get('areas',[])
    if areas:
        def one_area(x, h):
            out=[f"{h} {x.get('name','Area')}",'',sent(x.get('freedom')),'']
            if x.get('fixed_semantics'): out+=[lab(x,'fixed_semantics','Fixed semantics:'),'']+bullets(x['fixed_semantics'])+['']
            if x.get('document'): out+=[lab(x,'document','A conforming implementation must document:'),'']+bullets(x['document'])+['']
            return out
        L+=h2('Implementation-Defined Areas')+numbered(areas,sec[0],'###',one_area)
    ref=d['reference.yaml'].get('reference_implementation',{})
    if ref.get('summary'):
        L+=h2('Reference Implementation')+[sent(ref['summary']),'']
        if ref.get('normative') is False: L+=['The reference implementation is **not normative**; it is one realization of this specification.','']
    vm=verification_matrix_lines(d,idx,sec_no=sec[0]+1)
    if vm: L+=h2('Test and Validation Matrix')+vm
    cl=checklist_lines(d,params,sec_no=sec[0]+1)
    if cl: L+=h2('Implementation Checklist (Definition of Done)')+cl
    conf=['satisfies applicable normative semantics','preserves conceptual relationships and responsibility boundaries','implements the defined interactions and lifecycle semantics','preserves invariants and defined failure behavior','may choose different mechanisms where implementation freedom is declared','documents its selected behavior for every implementation-defined area','does not treat reference-specific choices as additional requirements']
    if params: conf.insert(4,'exposes every field in the configuration specification with its stated semantics')
    if any(x.get('conformance')=='extension' for x in all_records(d)): conf.append('may omit optional extensions entirely; every implemented extension is normative in full')
    L+=h2('Conformance')+[sent(d['manifest.yaml'].get('implementation_instruction')),'','A conforming implementation:','']+bullets(conf)+['']
    return resolve_sections('\n'.join(L).rstrip())+'\n'

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
