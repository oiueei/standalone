/**
 * Renders a subset of Markdown as sanitised HTML.
 *
 * Supported syntax:
 *   **bold**           -> <strong>
 *   *italic* / _italic_ -> <em>
 *   - bullet           -> <ul><li>
 *   1. numbered        -> <ol><li>
 *   [text](url)        -> <a> (http/https only)
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

function markdownToHtml(text) {
  if (!text) return '';

  const lines = text.split('\n');
  const output = [];
  let inUl = false;
  let inOl = false;

  for (const rawLine of lines) {
    const line = escapeHtml(rawLine);

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

export default function MarkdownText({ text, className = '' }) {
  if (!text) return null;
  const html = markdownToHtml(text);
  return (
    <div
      className={`markdown-text ${className}`.trim()}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
