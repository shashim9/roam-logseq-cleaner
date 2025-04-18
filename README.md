# roam_merge_dedupe.py

Merge multiple **Roam Research** or **Logseq** JSON / ZIP exports into a
_single_, duplicate‑free backup that Roam can import as a fresh graph.

IMPORTANT: All code (and this README) was written by ChatGPT o3. I've used this on my own graphs and it seems to work fine, but use at your own peril.

## Features

* **Date‑title normalisation** – `Sep 21st 2022` → `September 21st, 2022`
* **Readwise headers fixed** – all variants become `#highlights`
* **Global block deduplication** – identical blocks removed even if they
  were appended under different parents
* **Strip trailing YAML / Logseq footers** – everything after the first
  `---` bullet is dropped
* **New UIDs** for every kept page & block
* Accepts **Roam JSON** (old list or new dict style) and **Logseq ZIP/JSON**

Flags	| Meaning
-o, --output	Name of the merged file (default clean_graph.json)
-v, --verbose	Print one line per page (+ added, ↺ merged)
--keep-last	Keep the later duplicate block instead of the first
--dry-run	Do everything except write the output file


## Usage

```bash
python3 roam_merge_dedupe.py \
        export1.json export2.json export3.zip \
        -o clean_graph.json --verbose

Import into Roam
Create a brand‑new graph from Roam’s dashboard.

Drag clean_graph.json onto the page.

Wait for Roam to finish page creation and backlink indexing.


