import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
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
  test('says who lends it, where and when, on one line', () => {
    render(<NetworkPointLine point={POINT} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent(
      'Lent by Cooperativa La Fusteria · Carrer Major 4 · martes y jueves de 18 a 20'
    );
  });

  test('leaves out what the point did not fill in', () => {
    render(<NetworkPointLine point={{ display_name: 'Lele', address: '', hours_note: '' }} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent(/^Lent by Lele$/);
  });

  test('a dinamizador with no name at all is a member', () => {
    render(<NetworkPointLine point={{ display_name: '', address: 'Calle 1', hours_note: '' }} />);

    expect(screen.getByTestId('network-point-line')).toHaveTextContent(
      'Lent by A member · Calle 1'
    );
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
});
