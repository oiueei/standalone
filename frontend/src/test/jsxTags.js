import fs from 'node:fs';
import path from 'node:path';

/**
 * The walk the source sweeps share (`themedButtons.test.js`, `themedToggles.test.js`).
 *
 * **The tag is walked, not matched.** A regex like `<Button[^>]*>` stops at the `>` of
 * the `=>` in an `onClick={() => …}` and reads the rest of the props as absent, which
 * is a false alarm on every button with a handler. The walk keeps count of braces (and
 * of strings inside them), so only a `>` at the tag's top level ends it — and only what
 * sits at the top level counts, so a `style=` on an element nested in an attribute
 * (`icon={<Icon style={…} />}`) does not stand in for the tag's own.
 */

/**
 * Every `<Name …>` opening tag in `source`, as `{ line, top }`: `top` is the tag's top
 * level only — its attributes, each `{…}` folded to a marker (`{SPREAD}` for a spread).
 */
export function openingTags(source, name) {
  const found = [];
  const opening = new RegExp(`<${name}(?=[\\s/>])`, 'g');
  for (const match of source.matchAll(opening)) {
    const lineStart = source.lastIndexOf('\n', match.index) + 1;
    // A tag inside a comment (`// <Button …>`, a JSDoc line, `{/* … */}`) is prose.
    if (/\/\/|\/\*|^\s*\*/.test(source.slice(lineStart, match.index))) continue;

    let depth = 0;
    let quote = null; // the quote of a string being read, at any depth
    let top = ''; // the tag's top level only: attributes, with each {…} folded to a marker
    let i = match.index + `<${name}`.length;
    for (; i < source.length; i += 1) {
      const ch = source[i];
      if (quote) {
        if (ch === '\\') i += 1;
        else if (ch === quote) quote = null;
        if (depth === 0) top += ch;
        continue;
      }
      if (ch === '"' || ch === "'" || (ch === '`' && depth > 0)) {
        quote = ch;
        if (depth === 0) top += ch;
        continue;
      }
      if (ch === '{') {
        if (depth === 0)
          top += source
            .slice(i + 1)
            .trimStart()
            .startsWith('...')
            ? '{SPREAD}'
            : '{}';
        depth += 1;
        continue;
      }
      if (ch === '}') {
        depth -= 1;
        continue;
      }
      if (depth === 0) {
        if (ch === '>') break;
        top += ch;
      }
    }
    found.push({ line: source.slice(0, match.index).split('\n').length, top });
  }
  return found;
}

/** The `.jsx` sources under `dir` that are not tests. */
export function sourceFiles(dir, found = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) sourceFiles(full, found);
    else if (/\.jsx$/.test(entry.name) && !entry.name.includes('.test.')) found.push(full);
  }
  return found;
}
