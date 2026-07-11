// Shared CSV-parsing helpers for the bulk-import flows (bulk-add things,
// bulk-invite guests). Both feed these into PapaParse.
//
// Excel and Numbers in many locales (e.g. Spanish) export CSVs with ";" as the
// column separator — and Excel prepends a "sep=;" hint line that PapaParse does
// NOT honour (it parses that line as the header row, corrupting everything).
// Stripping that line and letting PapaParse auto-detect the delimiter makes both
// "," and ";" files just work, whatever the user's spreadsheet locale.

/** Remove a leading spreadsheet delimiter-hint line (`sep=;` / `sep=,`). */
export const stripSepLine = (chunk) => chunk.replace(/^sep=.*\r?\n/i, '');

/** Delimiters PapaParse should try when auto-detecting (comma, semicolon, tab). */
export const CSV_DELIMITERS = [',', ';', '\t'];

/**
 * Shared PapaParse base options for the bulk-import flows. `parseCsv` and the
 * in-ZIP `parseZip` path in BulkAddCsv both spread this and add their own
 * `complete`/`error` callbacks, so delimiter auto-detection and the Excel
 * `sep=;`-line stripping can never drift apart — a `;`-delimited CSV used to
 * parse correctly as a plain `.csv` yet fail inside a `.zip`, where the string
 * path omitted both options. PapaParse fires `beforeFirstChunk` for string input
 * too (StringStreamer → ChunkStreamer.parseChunk), so one base serves both.
 */
export const CSV_PARSE_OPTIONS = {
  header: true,
  skipEmptyLines: true,
  delimitersToGuess: CSV_DELIMITERS,
  beforeFirstChunk: stripSepLine,
  transformHeader: (header) => header.trim().toLowerCase(),
};
