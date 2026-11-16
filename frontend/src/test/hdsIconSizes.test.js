import { describe, test, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { openingTags, sourceFiles } from './jsxTags';

/**
 * `size` on an icon of `hds-react` takes `extraSmall | small | medium | large | extraLarge`.
 * Anything else (`"m"`, `"xs"`) adds no size class, so the icon is painted at the default
 * 24px whatever the code seems to ask for — a request that does nothing and reads as if it
 * did. OIUEEI's own icons (`components/icons/OiueeiIcons.jsx`) accept the short names as
 * well, so the sweep looks only at the ones imported from `hds-react` and at an icon held
 * in a variable named `…Icon` (a row's `icon`, always an HDS one).
 *
 * The two `IconCheck size="xs"` of the palette and wave selectors are written exceptions:
 * they have always been painted at 24px, and moving them to 16 would change how the
 * selectors look, which is a design decision. They go when that is decided.
 */
const VALID = new Set(['extraSmall', 'small', 'medium', 'large', 'extraLarge']);
const EXCEPTIONS = new Set([
  `${path.join('src', 'components', 'KoroSelector.jsx')}:IconCheck:xs`,
  `${path.join('src', 'components', 'TheeemeSelector.jsx')}:IconCheck:xs`,
]);

/** The icons a source imports from `hds-react`, plus the variables named `…Icon`. */
function hdsIconNames(source) {
  const names = new Set();
  for (const m of source.matchAll(/import\s*\{([^}]*)\}\s*from\s*'hds-react'/g)) {
    for (const part of m[1].split(',')) {
      const name = part
        .trim()
        .split(/\s+as\s+/)
        .pop();
      if (/^Icon[A-Z]/.test(name)) names.add(name);
    }
  }
  for (const m of source.matchAll(/<([A-Z][A-Za-z]*Icon)(?=[\s/>])/g)) names.add(m[1]);
  return [...names];
}

/** Every string `size="…"` an HDS icon tag carries, as `{ file, line, name, size }`. */
export function iconSizes(source, file = 'x.jsx') {
  const found = [];
  for (const name of hdsIconNames(source)) {
    for (const { line, top } of openingTags(source, name)) {
      const size = /(?:^|\s)size="([^"]*)"/.exec(top)?.[1];
      if (size !== undefined) found.push({ file, line, name, size });
    }
  }
  return found;
}

const bad = (tags) =>
  tags.filter((t) => !VALID.has(t.size) && !EXCEPTIONS.has(`${t.file}:${t.name}:${t.size}`));

describe('the walk over the icons of a source', () => {
  test('a short size on an HDS icon is caught, on one line or across several', () => {
    const source = `import { IconCamera } from 'hds-react';
      <IconCamera size="m" aria-hidden="true" />
      <IconCamera
        aria-hidden="true"
        size="xs"
      />`;
    expect(bad(iconSizes(source)).map((t) => [t.line, t.size])).toEqual([
      [2, 'm'],
      [3, 'xs'],
    ]);
  });

  test('HDS’s own names, and no size at all, are fine', () => {
    const source = `import { IconCamera } from 'hds-react';
      <IconCamera size="medium" /><IconCamera />`;
    expect(bad(iconSizes(source))).toEqual([]);
  });

  test('an icon of OIUEEI’s own, which takes the short names, is not looked at', () => {
    const source = `import { IconQrCode } from './icons/OiueeiIcons';
      <IconQrCode size="m" />`;
    expect(iconSizes(source)).toEqual([]);
  });

  test('an icon held in a variable named …Icon is an HDS one', () => {
    expect(bad(iconSizes('<RowIcon size="m" aria-hidden="true" />'))).toHaveLength(1);
  });

  test('a commented tag is not a tag', () => {
    expect(
      iconSizes(`import { IconCamera } from 'hds-react';\n// <IconCamera size="m" />`)
    ).toEqual([]);
  });
});

describe('every HDS icon in the app is asked for a size HDS knows', () => {
  test('no size="m" or "xs" in pages/ or components/, but the two written exceptions', () => {
    const files = [
      ...sourceFiles(path.join('src', 'pages')),
      ...sourceFiles(path.join('src', 'components')),
    ];
    const all = files.flatMap((file) => iconSizes(fs.readFileSync(file, 'utf8'), file));

    // The walk found the icons that carry a size: an empty sweep would pass for the wrong reason.
    expect(all.length).toBeGreaterThanOrEqual(2);
    expect(bad(all).map((t) => `${t.file}:${t.line} ${t.name} size="${t.size}"`)).toEqual([]);
    // Both exceptions are still in use; one that stopped being true is removed from the list.
    const used = new Set(all.map((t) => `${t.file}:${t.name}:${t.size}`));
    for (const e of EXCEPTIONS) expect(used.has(e)).toBe(true);
  });
});
