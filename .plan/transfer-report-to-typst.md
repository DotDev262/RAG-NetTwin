# Plan: Transfer Phase 1 Report to Typst Paper

The objective is to move the content from `Full_Phase_1_Report.md` into `Paper/main.typ`, following the provided Typst template.

## Proposed Changes

### 1. Update `Paper/main.typ`
- Replace template placeholders with the actual report title, abstract, keywords, acknowledgement, declaration, and abbreviations.
- Populate chapters with the content from the report:
    - **Introduction**: Chapters 1.1 to 1.8.
    - **Literature Review**: Chapters 2.1 to 2.4, including the Literature Summary Table.
    - **Dataset and Methodology**: Chapters 3.1 to 3.4.
    - **Result and Analysis**: Chapters 4.1 to 5.5, including performance tables and figures.
    - **Conclusion and Future Work**: Chapters 6.1 to 6.2.
- Convert Markdown formatting (bold, italics, lists) to Typst formatting.
- Convert Markdown tables to Typst `#table` calls.
- Convert images/figures to Typst `#figure` and `#image` calls.

### 2. (Optional but Recommended) Update `Paper/references.bib`
- Add the 20 references from the report to the bibliography file to allow proper citation in `main.typ`. *Note: I will only do this if requested or if I can find a way to map the labels easily.* I'll stick to just `main.typ` first as requested.

## Implementation Details

- **Title**: "VERSION-AWARE RAG FOR RELIABLE NETWORK CLI SYNTHESIS"
- **Authors**: Aryan (Registration Number placeholder)
- **Supervisor**: Placeholder (Guidance mentioned in report)
- **Degree**: Bachelor of Technology
- **Abstract**: Full text from report.
- **Keywords**: Extracted from report.
- **Acknowledgement**: Full text from report.
- **Declaration**: Full text from report.
- **Abbreviations**: Extracted from report.
- **Figures**: Reference `figure_chunking_sensitivity.png` and `results/performance_comparison.png`.

## Verification Steps
- Check that `main.typ` compiles or is syntactically correct for Typst.
- Verify that all major sections from the Markdown report are present in the Typst document.
- Ensure tables and figures are correctly formatted.
