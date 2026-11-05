import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import declarePalette from '../test/declarePalette';
import { declarations, declarationsInMedia, declared, rulesFor } from '../test/cssRules';
import NetworkPointLine from './NetworkPointLine';
import ThingInfoRows from './ThingInfoRows';

/**
 * A thing of a network says who lends it and where and when it is collected, from the
 * pickup point the server resolved for its owner. The name is the server's one
 * (`display_name`); the address and hours are shown as written.
 */
const POINT = {
  display_name: 'Cooperativa La Fusteria',
  address: 'Carrer Major 4',
  hours_note: 'martes y jueves de 18 a 20',
  contact: '93 000 00 00',
};

describe('NetworkPointLine', () => {
  test('says who lends it, where and when, one detail to a line', () => {
    render(<NetworkPointLine point={POINT} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent(
      'Lent by Cooperativa La Fusteria Carrer Major 4 martes y jueves de 18 a 20'
    );
  });

  test('leaves out what the point did not fill in', () => {
    render(<NetworkPointLine point={{ display_name: 'Lele', address: '', hours_note: '' }} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent(/^Lent by Lele$/);
  });

  test('a dinamizador with no name at all is a member', () => {
    render(<NetworkPointLine point={{ display_name: '', address: 'Calle 1', hours_note: '' }} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent('Lent by A member Calle 1');
  });

  test('shows the words as text, never as markup', () => {
    render(<NetworkPointLine point={{ display_name: '<b>x</b>', address: '', hours_note: '' }} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent('Lent by <b>x</b>');
    expect(document.querySelector('[data-testid="network-point-line"] b')).toBeNull();
  });

  test('nothing for a thing outside a network', () => {
    const { container } = render(<NetworkPointLine point={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  test('the thing’s info rows open with the line a view hands them', () => {
    const thing = { type: 'LEND_THING', network_point: POINT, fee: null, deposit: null };
    render(<ThingInfoRows thing={thing} isDateBased lead={<NetworkPointLine point={POINT} />} />);

    expect(screen.getByTestId('network-point-line')).toBeInTheDocument();
  });

  test('the lender is in bold and the address and the hours are a line each', () => {
    render(<NetworkPointLine point={POINT} />);

    const box = screen.getByTestId('network-point-line');
    expect(box.querySelector('strong')).toHaveTextContent('Lent by Cooperativa La Fusteria');
    const details = [...box.querySelectorAll('.network-point-detail')];
    expect(details.map((el) => el.textContent)).toEqual([
      'Carrer Major 4',
      'martes y jueves de 18 a 20',
    ]);
  });

  test('a detail the point left empty paints no element', () => {
    render(<NetworkPointLine point={{ ...POINT, address: '' }} />);

    const details = screen
      .getByTestId('network-point-line')
      .querySelectorAll('.network-point-detail');
    expect([...details].map((el) => el.textContent)).toEqual(['martes y jueves de 18 a 20']);
  });

  test('the pin is hidden from a screen reader and the box leads nowhere', () => {
    render(<NetworkPointLine point={POINT} />);

    const box = screen.getByTestId('network-point-line');
    expect(box.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(box.querySelector('a, button')).toBeNull();
    expect(box.hasAttribute('role')).toBe(false);
  });

  test('the frame takes the hero colour of the palette in force', () => {
    declarePalette(
      {
        color_01: 'coat-of-arms',
        color_02: 'gold-light',
        color_03: 'engel',
        color_04: 'black',
        color_05: 'black',
        color_06: 'white',
      },
      'basic'
    );
    render(<NetworkPointLine point={POINT} />);

    expect(screen.getByTestId('network-point-line').style.borderColor).toBe('var(--color-engel)');
  });

  test('with no palette declared the frame is the app’s own hero colour', () => {
    render(<NetworkPointLine point={POINT} />);

    expect(screen.getByTestId('network-point-line').style.borderColor).toBe(
      'var(--color-braaanding-03)'
    );
  });

  test('the stylesheet gives the box an 8px frame and 24px under it', () => {
    expect(declarations('.network-point', 'border')).toEqual(['8px solid var(--color-black-20)']);
    expect(declarations('.network-point', 'margin')).toEqual([
      'var(--spacing-2-xs) 0 var(--spacing-m)',
    ]);
  });

  test('with a logo the image is the last thing in the box and the pin stays first', () => {
    render(<NetworkPointLine point={{ ...POINT, logo_url: 'https://cdn/fusteria.png' }} />);

    const box = screen.getByTestId('network-point-line');
    const img = box.querySelector('img');
    expect(img).toHaveAttribute('src', 'https://cdn/fusteria.png');
    expect(img).toHaveAttribute('alt', '');
    expect(img.className).toBe('network-point-logo');
    expect(box.lastElementChild).toBe(img);
    expect(box.firstElementChild.tagName.toLowerCase()).toBe('svg');
  });

  test('without a logo there is no image', () => {
    render(<NetworkPointLine point={{ ...POINT, logo_url: null }} />);

    expect(screen.getByTestId('network-point-line').querySelector('img')).toBeNull();
  });

  test('the logo is 48px tall and is never cropped', () => {
    expect(declarations('.network-point-logo', 'height')).toContain('48px');
    expect(declarations('.network-point-logo', 'width')).toEqual(['auto']);
    expect(declarations('.network-point-logo', 'max-width')).toContain('96px');
    expect(declarations('.network-point-logo', 'object-fit')).toEqual(['contain']);
    expect(declarations('.network-point-logo', 'margin-left')).toEqual(['auto']);
    expect(declarations('.network-point-logo', 'flex')).toEqual(['0 0 auto']);
  });

  test('from 768px the logo is 72px tall, up to 144px wide; below it stays 48 and 96', () => {
    const media = '(min-width: 768px)';
    expect(declarationsInMedia(media, '.network-point-logo', 'height')).toEqual(['72px']);
    expect(declarationsInMedia(media, '.network-point-logo', 'max-width')).toEqual(['144px']);
    // the first rule found is the base one, outside any media query
    const base = rulesFor('.network-point-logo')[0];
    expect(declared(base, 'height')).toBe('48px');
    expect(declared(base, 'max-width')).toBe('96px');
  });
});
