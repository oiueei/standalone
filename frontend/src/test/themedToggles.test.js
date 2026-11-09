import { describe, test, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { openingTags, sourceFiles } from './jsxTags';

/**
 * A switch that is on paints HDS's default blue unless it carries the palette's
 * colour, `useTheeeme().toggleTheme`. Like a bare `<Button>`, a bare `<ToggleButton>`
 * works, is labelled and passes axe, so nothing else sees it: the source is swept.
 *
 * Every `<ToggleButton …>` opening tag in `pages/` and `components/` must carry
 * `theme=` — except a literal `disabled` one: the profile's always-on switch
 * ("sign-in links and invitations") is HDS's own grey on purpose.
 */

const isThemed = ({ top }) => /(^|\s)theme=/.test(top);
const isDisabled = ({ top }) => /(^|\s)disabled(?=\s|$)/.test(top);
const bare = (source) =>
  openingTags(source, 'ToggleButton').filter((tag) => !isThemed(tag) && !isDisabled(tag));

describe('the walk over a ToggleButton tag', () => {
  test('a theme after a handler’s arrow is seen', () => {
    expect(bare('<ToggleButton onChange={(v) => set(!v)} theme={toggleTheme} />')).toEqual([]);
  });

  test('a toggle with no theme is caught, across lines', () => {
    const source = `
      <ToggleButton
        id="x"
        onChange={() => set()}
      />`;
    expect(bare(source).map((tag) => tag.line)).toEqual([2]);
  });

  test('a literal disabled toggle is the written exception, a computed one is not', () => {
    expect(bare('<ToggleButton id="x" checked disabled onChange={() => {}} />')).toEqual([]);
    expect(bare('<ToggleButton id="x" disabled={busy} onChange={() => {}} />')).toHaveLength(1);
  });

  test('a theme on something nested in an attribute is not the toggle’s own', () => {
    expect(bare('<ToggleButton label={<Tip theme={x} />} />')).toHaveLength(1);
  });
});

describe('every HDS ToggleButton in the app paints in the palette in force', () => {
  test('no bare <ToggleButton> in pages/ or components/', () => {
    const files = [
      ...sourceFiles(path.join('src', 'pages')),
      ...sourceFiles(path.join('src', 'components')),
    ];
    let examined = 0;
    const offenders = [];
    for (const file of files) {
      for (const tag of openingTags(fs.readFileSync(file, 'utf8'), 'ToggleButton')) {
        examined += 1;
        if (!isThemed(tag) && !isDisabled(tag)) offenders.push(`${file}:${tag.line}`);
      }
    }

    // The walk found the toggles: an empty sweep would pass for the wrong reason.
    expect(examined).toBeGreaterThanOrEqual(12);
    expect(offenders).toEqual([]);
  });
});
