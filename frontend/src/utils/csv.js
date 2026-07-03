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
