/**
 * Renders a subset of Markdown as sanitised HTML.
 *
 * Supported syntax:
 *   **bold**           -> <strong>
 *   *italic* / _italic_ -> <em>
 *   - bullet           -> <ul><li>
 *   1. numbered        -> <ol><li>
 *   [text](url)        -> <a> (http/https only)
 *   | a | b | pipe tables (GFM: header row + |---|---| separator) -> <table>
 *   # / ## / ###+ heading -> <h3> / <h4> / <h5> (deeper levels cap at <h5> —
 *     the page around this component already owns h1/h2, so a bio can't
 *     outrank the page's own outline)
 *
 * All other content is HTML-escaped before processing.
 */

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function sanitizeUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return ['http:', 'https:'].includes(parsed.protocol) ? url : '#';
  } catch {
    return '#';
  }
}

function renderInline(text) {
  // Links: [text](url)
  let result = text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_, label, url) => `<a href="${escapeHtml(sanitizeUrl(url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`
  );
  // Bold: **text**
  result = result.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text* or _text_
  result = result.replace(/(?<!\w)\*(.+?)\*(?!\w)/g, '<em>$1</em>');
  result = result.replace(/(?<!\w)_(.+?)_(?!\w)/g, '<em>$1</em>');
  return result;
}

// GFM pipe-table line shapes. The separator row (|---|---|, optional colons)
// carries no escapable characters, so it can be tested on the raw line.
const isTableRow = (l) => /^\s*\|.*\|\s*$/.test(l);
const isTableSeparator = (l) => /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(l);
const tableCells = (escapedLine) => {
  const trimmed = escapedLine.trim();
  return trimmed.slice(1, -1).split('|').map((c) => c.trim());
};

function markdownToHtml(text, headingBase = 3) {
  if (!text) return '';

  const lines = text.split('\n');
  const output = [];
  let inUl = false;
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = escapeHtml(rawLine);

    // Pipe table: a |header| row immediately followed by a |---| separator row.
    // Cells are escaped (via `line`) before splitting, then get inline rendering.
    if (isTableRow(rawLine) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      if (inUl) { output.push('</ul>'); inUl = false; }
      if (inOl) { output.push('</ol>'); inOl = false; }
      const header = tableCells(line).map((c) => `<th>${renderInline(c)}</th>`).join('');
      const bodyRows = [];
      let j = i + 2;
      while (j < lines.length && isTableRow(lines[j]) && !isTableSeparator(lines[j])) {
        const cells = tableCells(escapeHtml(lines[j])).map((c) => `<td>${renderInline(c)}</td>`);
        bodyRows.push(`<tr>${cells.join('')}</tr>`);
        j++;
      }
      output.push(
        `<div class="markdown-table-wrap"><table><thead><tr>${header}</tr></thead>` +
          `<tbody>${bodyRows.join('')}</tbody></table></div>`
      );
      i = j - 1;
      continue;
    }

    // Heading: # / ## / ###+ text -> h{base} / h{base+1} / h{base+2} (capped).
    // The default base is 3 (a bio inside a page that already owns h1/h2);
    // a page whose markdown IS the content (LegalPage) passes base 2 so the
    // outline doesn't skip a level (axe heading-order).
    const headingMatch = line.match(/^(#{1,6}) (.+)$/);
    if (headingMatch) {
      if (inUl) { output.push('</ul>'); inUl = false; }
      if (inOl) { output.push('</ol>'); inOl = false; }
      const tag = `h${Math.min(headingMatch[1].length, 3) + headingBase - 1}`;
      output.push(`<${tag}>${renderInline(headingMatch[2])}</${tag}>`);
      continue;
    }

    // Unordered list: - text
    const ulMatch = line.match(/^- (.+)$/);
    if (ulMatch) {
      if (inOl) { output.push('</ol>'); inOl = false; }
      if (!inUl) { output.push('<ul>'); inUl = true; }
      output.push(`<li>${renderInline(ulMatch[1])}</li>`);
      continue;
    }

    // Ordered list: 1. text
    const olMatch = line.match(/^\d+\. (.+)$/);
    if (olMatch) {
      if (inUl) { output.push('</ul>'); inUl = false; }
      if (!inOl) { output.push('<ol>'); inOl = true; }
      output.push(`<li>${renderInline(olMatch[1])}</li>`);
      continue;
    }

    // Close any open list
    if (inUl) { output.push('</ul>'); inUl = false; }
    if (inOl) { output.push('</ol>'); inOl = false; }

    if (line.trim() === '') {
      output.push('<br/>');
    } else {
      output.push(`<span>${renderInline(line)}</span>`);
    }
  }

  if (inUl) output.push('</ul>');
  if (inOl) output.push('</ol>');

  return output.join('');
}

// eslint-disable-next-line react-refresh/only-export-components -- pure helpers co-located for unit tests (markdown.test.jsx) and reuse (sanitizeUrl on ThingPage)
export { markdownToHtml, sanitizeUrl };

export default function MarkdownText({ text, className = '', headingBase = 3 }) {
  if (!text) return null;
  const html = markdownToHtml(text, headingBase);
  return (
    <div
      className={`markdown-text ${className}`.trim()}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
