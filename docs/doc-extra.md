# Extra documents (not yet in the RAG corpus)

Found while checking whether newer building/development-control documents exist
beyond the base TNCDRBR 2019 text used in `docs/chunks.json`. **Not ingested
into the pipeline yet** — shelved here for later.

## Why these matter

TNCDRBR 2019 (our current `primary` building-regulation source) has been
amended 13 times by CMDA/Housing & Urban Development Dept since 2020, most
recently October 2025. Two of these amendments are operationally significant
and would change answers our current `validate.py` gives:

- **G.O. Ms. No. 225, dated 26 Nov 2024** — removes height restrictions for
  high-rise buildings on roads ≥30m wide, on plots ≥4,000 sq.m, subject to
  Airport Authority of India (AAI) clearance. Directly relevant to our
  `height_restrictions` and `airport_noc`-type findings.
- **G.O. Ms. No. 58 / 69 / 70, dated 5/11 March 2024** — removes the
  completion-certificate requirement for residential buildings up to 14m
  height, ≤8 dwelling units or ≤750 sq.m; also revises setback and rainwater
  harvesting provisions.

## Status: downloaded, not ingested

All 13 amendment PDFs were downloaded from CMDA's official site into
`docs/amendments/`. Source page: https://www.cmdachennai.gov.in/TNCDBR2019.html

| File | Date | Extracts cleanly? | Notes |
|---|---|---|---|
| Amendment_GO_Ms_No_16_Dated_31_01_2020.pdf | 2020-01-31 | ✅ yes (98% ascii) | |
| Amendment_GO_Ms_No_51_Dated_11_05_2020.pdf | 2020-05-11 | ✅ yes (98% ascii) | |
| Amendment_GO_Ms_No_152_Dated_18_08_2022.pdf | 2022-08-18 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_15_Dated_14_01_2024.pdf | 2024-01-14 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_58_Dated_05_03_2024.pdf | 2024-03-05 | ❌ scanned/garbled | needs OCR — completion certificate exemption |
| Amendment_GO_Ms_No_69_Dated_11_03_2024.pdf | 2024-03-11 | ❌ scanned/garbled | needs OCR — completion certificate exemption |
| Amendment_GO_Ms_No_70_Dated_11_03_2024.pdf | 2024-03-11 | ❌ scanned/garbled | needs OCR — completion certificate exemption |
| GO_225_2024-11-26.pdf | 2024-11-26 | ⚠️ partial (75% ascii) | needs OCR — height restriction removal (AAI clearance) |
| Amendment_GO_Ms_No_107_Dated_16_07_2025.pdf | 2025-07-16 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_154_Dated_07_10_2025.pdf | 2025-10-07 | ✅ yes (97% ascii) | 30 pages |
| Amendment_GO_Ms_No_155_Dated_08_10_2025.pdf | 2025-10-08 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_156_Dated_10_10_2025.pdf | 2025-10-10 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_161_Dated_15_10_2025.pdf | 2025-10-15 | ❌ scanned/garbled | needs OCR |
| Amendment_GO_Ms_No_171_Dated_30_10_2025.pdf | 2025-10-30 | ✅ yes (97% ascii) | EV charging infrastructure requirement, confirmed readable |

**Cause of the garbling:** these gazette PDFs use a non-standard/embedded font
encoding (common with Tamil Nadu Government Gazette scans) that breaks
`pypdf`'s naive text extraction — the header/title lines extract fine but body
text comes out as mixed symbols. Fixing this needs OCR (Tesseract +
`pytesseract`/`pdf2image`), which is not installed in this environment.

## To pick this back up later

1. Install Tesseract OCR binary + `pytesseract` and `pdf2image` (`pip install
   pytesseract pdf2image`).
2. OCR the 8 garbled PDFs (list above) page-by-page, same chunking approach
   as `src/ingest.py`.
3. Add them to `SOURCE_META` in `src/ingest.py` with `authority: "primary"`
   (they supersede the relevant sections of TNCDRBR 2019 base text) and a
   note that they're amendments, not the base document.
4. Re-run `python src/ingest.py` and `python src/embed.py`.
5. Consider whether `validate.py`'s authority-preference logic needs a
   "amendment overrides base rule on same topic" tier, not just
   "primary vs superseded" — an amendment and the 2019 base text are both
   nominally primary but the amendment should win when they conflict.
