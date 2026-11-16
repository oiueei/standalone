import { render } from '@testing-library/react';
import { IconCamera } from 'hds-react';
import { describe, test, expect } from 'vitest';
import {
  IconMyRequests,
  IconRequestsToMe,
  IconTheeemes,
  IconInviteMany,
  IconQrCode,
  IconGeneral,
} from './OiueeiIcons';

const ICONS = {
  IconMyRequests,
  IconRequestsToMe,
  IconTheeemes,
  IconInviteMany,
  IconQrCode,
  IconGeneral,
};
const SIZES = [
  ['xs', 'extraSmall', '0 0 16 16'],
  ['s', 'small', '0 0 24 24'],
  ['m', 'medium', '0 0 32 32'],
  ['l', 'large', '0 0 48 48'],
  ['xl', 'extraLarge', '0 0 64 64'],
];

const svgOf = (node) => render(node).container.querySelector('svg');
const classesOf = (node) => svgOf(node).getAttribute('class');

describe.each(Object.entries(ICONS))('%s', (_name, Component) => {
  const Icon = Component;
  test('is a decorative currentColor svg by default', () => {
    const svg = svgOf(<Icon />);
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('role')).toBe('img');
    const paths = svg.querySelectorAll('path');
    expect(paths.length).toBeGreaterThan(0);
    paths.forEach((p) => {
      expect(p.getAttribute('fill')).toBe('currentColor');
      expect(p.getAttribute('fill-rule')).toBe('evenodd');
    });
  });

  test('wears the classes an HDS icon of the same size wears, whatever the size', () => {
    expect(classesOf(<Icon />)).toBe(classesOf(<IconCamera />));
    for (const [short, hds] of SIZES) {
      expect(classesOf(<Icon size={short} />)).toBe(classesOf(<IconCamera size={hds} />));
      expect(classesOf(<Icon size={hds} />)).toBe(classesOf(<IconCamera size={hds} />));
    }
  });

  test('keeps the caller’s className, style, aria-label and aria-hidden, and passes other props on', () => {
    const svg = svgOf(
      <Icon
        className="mine"
        style={{ color: 'red' }}
        aria-label="named"
        aria-hidden={false}
        data-x="1"
      />
    );
    expect(svg.getAttribute('class')).toMatch(/\bmine\b/);
    expect(svg.style.color).toBe('red');
    expect(svg.getAttribute('aria-label')).toBe('named');
    expect(svg.getAttribute('aria-hidden')).toBe('false');
    expect(svg.getAttribute('data-x')).toBe('1');
  });
});

describe('IconQrCode', () => {
  test.each(SIZES)('draws its own pattern at %s', (short, _hds, viewBox) => {
    expect(svgOf(<IconQrCode size={short} />).getAttribute('viewBox')).toBe(viewBox);
  });

  test('every size has a different drawing', () => {
    const drawn = SIZES.map(([s]) =>
      svgOf(<IconQrCode size={s} />)
        .querySelector('path')
        .getAttribute('d')
    );
    expect(new Set(drawn).size).toBe(SIZES.length);
  });
});

describe('the five that scale', () => {
  test.each(['xs', 's', 'm', 'l', 'xl'])('keep the 24 viewBox at %s', (size) => {
    for (const Icon of [
      IconMyRequests,
      IconRequestsToMe,
      IconTheeemes,
      IconInviteMany,
      IconGeneral,
    ]) {
      expect(svgOf(<Icon size={size} />).getAttribute('viewBox')).toBe('0 0 24 24');
    }
  });
});
