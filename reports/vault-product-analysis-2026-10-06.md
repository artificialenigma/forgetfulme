# Vault findings and Forgetful Me improvements

Date: 6 October 2026

## Scope and method

Scanned every Markdown file under `/Users/fa-001524/Documents/llm-wiki/llm-wiki`, including body text, headings, metadata, links, source references and file sizes. Examined representative content and compared requirements against the current app implementation. This is a corpus and product analysis, not an external fact-check of every claim. Word counts are approximate lexical counts and include code and scraped boilerplate. Hidden tool files are excluded from the main totals. No source notes were changed or transmitted to an AI provider.

## Corpus statistics

| Measure | Count |
|---|---:|
| All Markdown files, including hidden tool directories | 366 |
| Visible Markdown notes | 356 |
| Structured research wiki notes | 240 |
| Source notes | 87 |
| Concept-folder notes | 79 |
| Entity-folder notes | 66 |
| Filed analyses | 7 |
| Overview | 1 |
| Visible raw Markdown files | 80 |
| Clippings | 30 |
| Root Markdown files | 6 |
| Approximate visible words | 537,120 |
| Approximate research wiki words | 131,146 |
| Wiki pages with Connections sections | 219 (91%) |
| Wiki pages with Open questions sections | 85 (35%) |
| Source notes under 150 body words | 9 |
| Source notes without a literal HTTP URL in their text | 41 |
| Source notes without a detected raw-file reference | 15 |
| Clippings under 80 body words | 8 |
| Empty-body wiki pages | 2 |
| Entity-folder notes declared as concepts | 4 |

The 41 URL-free source notes are not necessarily untraceable: many reference local PDFs, articles or datasets. The raw-reference count is a text heuristic, not a complete provenance audit. Folder counts and frontmatter types differ because four entity-folder notes identify themselves as concepts.

## What the notes show

The collection supports ongoing research projects rather than only saving visited pages. The largest recurring themes are Maldives research, Game Boy development, AI workflows and personal knowledge management, ESP32 hardware, web development and cybersecurity. Common tags include Maldives (52 notes), game-boy and retro-computing (41 each), gbdk (29), open-source (26), llm (22) and esp32 (16); counts overlap.

The wiki's value is its connected synthesis. Connections appear on 219 pages, and 85 preserve research questions. Seven analyses combine material to answer questions about hardware architectures, crime research, media outlets, editors and wiki workflows. The app currently provides website and date organization but does not expose these project structures.

Source reliability varies. Nine source notes are under 150 words, including placeholders. Two React pages contain frontmatter only. The crime synthesis acknowledges indirect extraction of police statistics, and several notes distinguish marketing assertions, transcript errors, tentative conclusions and missing evidence. These distinctions should remain visible in retrieval and generated answers.

A concrete failed capture is `raw/articles/unicef-juvenile-justice.pdf`: its bytes begin with HTML rather than a PDF header. Its source note explicitly says no extractable claims were available. Filename or successful download alone is insufficient proof of successful capture.

The largest raw notes exceed 500 KB. One agent-skills clipping is 373 KB despite only about 2,950 lexical words because it includes embedded image data. Long catalogs, scripts and navigation can inflate content without improving usefulness. The current app summarizes the first 18,000 characters and answers from the first 5,000 characters of up to three captures; this can select boilerplate and omit relevant later sections.

The imported files are preserved by the app but not indexed into its question-answering corpus. `answer_one` searches only completed AI summaries in `page_captures`. Local research, raw attachments, concept pages and filed analyses are excluded. Queries are reduced to ASCII words, which also limits accented names and Dhivehi retrieval.

The stack comparison found identical content across all 1,200 visible imported files, but ten clipping filenames were corrupted during transfer. Unicode filename preservation is therefore a real import requirement. Earlier link scans also found missing entities, inconsistent paths and ambiguous short links; their automated totals include examples and scraped text and should not be treated as confirmed broken-link counts.

## Prioritized product changes

| Priority | Improvement | Why this corpus needs it | Acceptance check |
|---|---|---|---|
| 1 | Index imported notes locally | The existing research wiki cannot participate in app Q&A | Search returns imported concepts and sources while AI is disabled; cloud use requires explicit scope selection |
| 1 | Capture quality and exclusion controls | Empty clippings, HTML disguised as PDF, login and redirect captures | Flag incorrect MIME/signatures, empty extraction and auth pages; show repair actions and reasons |
| 1 | Chunk retrieval by headings | Long documents and boilerplate defeat prefix-only excerpts | A query retrieves a relevant section beyond character 18,000 and cites that section |
| 1 | Preserve Unicode during import | Ten filenames were damaged despite intact content | Round-trip accented, curly-quote and em-dash filenames without changes |
| 2 | Unified library and project views | Imported wiki and browsing archive are disconnected | One search spans both, with filters for project, type, tag, origin and review status |
| 2 | Evidence and provenance fields | Reports, data, marketing pages and drafts have different authority | Display original file/URL, publisher, source date, capture date, extraction status and draft/review status |
| 2 | Vault health page | Empty notes, inconsistent types and unresolved links are otherwise hidden | Show actionable diagnostics with previews; preserve source files until a repair is selected |
| 2 | Suggested connections with review | Rich manual connections are valuable; automatic fan-out previously created noise | Suggest links to existing pages first, display evidence, and require review before writing |
| 2 | Open-question inbox | 85 wiki pages already record research gaps | List questions with originating note; resolving one links to evidence and a saved answer |
| 3 | Attachment extraction and citations | PDFs, datasets, code and transcripts are important sources | Local extraction supports PDF page numbers, JSON field paths and code line citations |
| 3 | Freshness and contradiction review | Notes contain old figures, technical versions and explicit caveats | Flag potentially dated claims and conflicting excerpts with dates; do not silently rewrite |
| 3 | Knowledge-focused dashboard | Service health does not describe research usefulness | Show searchable notes, quality failures, evidence coverage, pending reviews and completed research questions |

Begin with local indexing, quality checks and chunk retrieval. A semantic search layer can follow after a representative benchmark shows what keyword search misses. Preserve user-owned notes, retain reviewed-note protection, and make any cross-source synthesis a reviewable draft. Do not restore unrestricted automatic concept/entity creation.

## Suggested retrieval benchmark

Use questions from this corpus: compare ESP32 intercom and mesh approaches; locate Game Boy sprite and palette examples; distinguish official Maldives statistics from perception surveys; find missing evidence for juvenile justice; identify unanswered questions about wiki search. Include queries with accents and Dhivehi, relevant passages near the end of long documents, and deliberately failed captures. Measure retrieved evidence relevance, citation correctness, abstention on absent evidence and whether imported notes are actually included.
