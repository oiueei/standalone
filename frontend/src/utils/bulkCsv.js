/**
 * Pure CSV-row mapping and validation for the bulk-add flow (BulkAddCsv).
 *
 * Kept i18n-free and component-free so the parsing/validation rules can be unit
 * tested directly. The component wraps `validateRows` to turn the returned key
 * into translated copy. Server-side validators still reject HTML, line breaks
 * and spreadsheet-formula injection per field — this layer only shapes rows and
 * enforces the client-side bounds.
 */

export const MAX_ROWS = 100;

// The plain text/scalar columns a CSV can carry. `tags` is a single
// `|`-separated cell and `photo` is a filename — both handled separately.
const COLUMNS = ['type', 'headline', 'description', 'fee', 'availability', 'location', 'condition'];

/**
 * Map one parsed CSV record to a row payload. `withPhoto` keeps the `photo`
 * filename for later Cloudinary resolution (ZIP path only). Empty/whitespace
 * cells are dropped so they don't overwrite server defaults.
 */
export function mapRow(raw, withPhoto) {
  const row = {};
  for (const col of COLUMNS) {
    const value = raw[col];
    if (value !== undefined && String(value).trim() !== '') {
      row[col] = String(value).trim();
    }
  }
  // Tags are a single cell holding a `|`-separated list (pipe avoids clashing
  // with the CSV field delimiter, which is `;` in some locales).
  if (raw.tags !== undefined && String(raw.tags).trim() !== '') {
    const tags = String(raw.tags).split('|').map((tag) => tag.trim()).filter(Boolean);
    if (tags.length > 0) row.tags = tags;
  }
  if (withPhoto && raw.photo !== undefined && String(raw.photo).trim() !== '') {
    row.photo = String(raw.photo).trim();
  }
  return row;
}

/**
 * Shared bounds/required checks. Returns an error KEY ('empty' | 'tooMany' |
 * 'headlineRequired') or null when the rows pass. The caller maps the key to copy.
 */
export function validateRows(parsed) {
  if (parsed.length === 0) return 'empty';
  if (parsed.length > MAX_ROWS) return 'tooMany';
  if (parsed.some((row) => !row.headline)) return 'headlineRequired';
  return null;
}
