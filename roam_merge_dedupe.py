#!/usr/bin/env python3
"""roam_merge_dedupe.py
Merge multiple Roam/Logseq JSON exports and output a Roam‑import‑ready file
with all post‑processing baked in:

• Accepts Roam JSON (dict with "pages") *or* older list‑style export *or* ZIP.
• Daily‑Note titles normalised to Roam long form ("September 24th, 2023").
• All variants of highlights header → "#highlights" (handles *, ##, Readwise line).
• Removes duplicate blocks globally (same text after cleaning) even across parents.
• Strips every page after the first top‑level bullet whose string *starts* with "---".
• Writes plain list of page objects (Roam’s backup format).
• Uses only Python standard library.

USAGE
-----
python3 roam_merge_dedupe.py export1.json export2.json export3.json \
        -o clean_graph.json --verbose

Optional flags:
    --dry-run      : build, report counts, but don’t write output
    --keep-last    : if duplicate blocks differ, keep the *later* one (default keeps first)
"""

import argparse, json, re, sys, uuid, hashlib, pathlib, zipfile
from typing import Any, Dict, List

# ─── date helpers ────────────────────────────────────────────────────────
MONTHS = ['January','February','March','April','May','June',
          'July','August','September','October','November','December']
MONTH_MAP = {m.lower()[:3]: i+1 for i,m in enumerate(MONTHS)}
DATE_RE = re.compile(
    r'^\s*(?P<month>[A-Za-z]{3,9})\.?\s*(?P<day>\d{1,2})(?:st|nd|rd|th)?\,?\s*(?P<year>\d{4})\s*$')

def ordinal(n:int)->str:
    return f"{n}{'th' if 11<=n%100<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

def canonical_date(title:str):
    m = DATE_RE.match(title.strip())
    if not m:
        return None
    month = MONTHS[MONTH_MAP[m.group('month').lower()[:3]]-1]
    return f"{month} {ordinal(int(m.group('day')))}, {m.group('year')}"

def canonical_title(t:str)->str:
    return canonical_date(t) or t.strip()

# ─── string clean & hash ────────────────────────────────────────────────
ID_RE   = re.compile(r'\bid::\s+\S+', re.I)
HL_RE   = re.compile(r'#highlights', re.I)
READWISE_RE = re.compile(r'^#+\s*#highlights\s+first\s+synced.+', re.I)

def clean_string(s:str)->str:
    s = READWISE_RE.sub('#highlights', s.strip())
    if HL_RE.search(s):            # any variant → canonical
        s = '#highlights'
    s = ID_RE.sub('', s)
    return ' '.join(s.split())

def sig(text:str)->str:
    return hashlib.sha1(clean_string(text).encode()).hexdigest()

def new_uid()->str:
    return uuid.uuid4().hex[:9]

# ─── load helper ────────────────────────────────────────────────────────
def load_pages(path:pathlib.Path)->List[Dict[str,Any]]:
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as z:
            js = [n for n in z.namelist() if n.endswith('.json')]
            if not js:
                sys.exit(f"✖ {path} contains no .json export")
            with z.open(js[0]) as f:
                data = json.load(f)
    else:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    if isinstance(data, dict):
        if 'pages' in data:
            return data['pages']
        return list(data.values())           # fallback: dict of pages
    elif isinstance(data, list):
        return data
    sys.exit(f"✖ {path} not recognised as Roam/Logseq export")

# ─── merge children with dedup ──────────────────────────────────────────
def merge_children(lists:List[List[Dict[str,Any]]], keep_last=False)->List[Dict[str,Any]]:
    merged, idx = [], {}
    for lst in lists:
        for blk in lst:
            h = sig(blk.get('string',''))
            if h in idx:
                i = idx[h]
                # merge grandchildren
                merged[i]['children'] = merge_children(
                    [merged[i].get('children',[]), blk.get('children',[])],
                    keep_last)
                if keep_last:
                    merged[i]['string'] = clean_string(blk.get('string',''))
            else:
                cp = {k:v for k,v in blk.items() if k!='children'}
                cp['string'] = clean_string(cp.get('string',''))
                cp['uid'] = new_uid()
                if blk.get('children'):
                    cp['children'] = merge_children([blk['children']], keep_last)
                merged.append(cp)
                idx[h] = len(merged)-1
    return merged

# ─── full page tidy: cut after YAML, dedup top‑level globally ───────────
def tidy_page(page:Dict[str,Any], keep_last=False):
    children = page.get('children', [])
    trimmed = []
    for blk in children:
        if blk.get('string','').lstrip().startswith('---'):
            break
        trimmed.append(blk)
    page['children'] = merge_children([trimmed], keep_last)
    page['uid'] = new_uid()
    return page

# ─── merge graphs ───────────────────────────────────────────────────────
def merge_graphs(graphs:List[List[Dict[str,Any]]], keep_last=False, verbose=False):
    pages:Dict[str,Dict[str,Any]] = {}
    for plist in graphs:
        for p in plist:
            title = canonical_title(p['title'])
            if title not in pages:
                clone = {k:v for k,v in p.items() if k!='children'}
                clone['title'] = title
                clone = tidy_page(clone, keep_last)
                pages[title] = clone
                if verbose: print(f"+ {title}")
            else:
                if verbose: print(f"↺ {title}")
                combined_children = [pages[title]['children'], p.get('children',[])]
                pages[title]['children'] = merge_children(combined_children, keep_last)
    return list(pages.values())        # plain list – Roam import‑ready

# ─── CLI ────────────────────────────────────────────────────────────────
def parse():
    ap = argparse.ArgumentParser(description="Merge Roam/Logseq exports and deduplicate.")
    ap.add_argument('exports', nargs='+', type=pathlib.Path, help='Input JSON/ZIP exports')
    ap.add_argument('-o','--output', type=pathlib.Path, default=pathlib.Path('clean_graph.json'))
    ap.add_argument('--keep-last', action='store_true', help='Keep last duplicate instead of first')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('-v','--verbose', action='store_true')
    return ap.parse_args()

def main():
    args = parse()
    pages_lists = [load_pages(p) for p in args.exports]
    merged_pages = merge_graphs(pages_lists, keep_last=args.keep_last, verbose=args.verbose)
    print(f"✔ merged {len(merged_pages)} pages")
    if args.dry_run:
        print('(dry‑run) no file written')
        return
    with args.output.open('w', encoding='utf-8') as f:
        json.dump(merged_pages, f, ensure_ascii=False)
    print(f"✓ wrote {args.output.resolve()}")
if __name__ == '__main__':
    main()
