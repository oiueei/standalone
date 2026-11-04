import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import FieldNotice from './FieldNotice';

expect.extend(toHaveNoViolations);

const EXAMPLE = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}';

function renderNotice() {
  return render(
    <FieldNotice id="n1" label="About languages" example={EXAMPLE} after="Second paragraph.">
      First paragraph.
    </FieldNotice>
  );
}

describe('FieldNotice', () => {
  afterEach(() => vi.restoreAllMocks());

  test('shows the first paragraph, the code example and the second paragraph', () => {
    renderNotice();

    expect(screen.getByText('First paragraph.')).toBeInTheDocument();
    const code = screen.getByText(EXAMPLE);
    expect(code.tagName).toBe('CODE');
    expect(code).toHaveClass('localized-example');
    expect(screen.getByText('Second paragraph.')).toBeInTheDocument();
  });

  test('leaves out the example and the second paragraph when none is given', () => {
    const { container } = render(
      <FieldNotice id="n2" label="Plain">
        Only this.
      </FieldNotice>
    );

    expect(screen.getByText('Only this.')).toBeInTheDocument();
    expect(container.querySelector('code')).toBeNull();
    expect(container.querySelectorAll('p')).toHaveLength(1);
  });

  test('the close button removes the notice', async () => {
    renderNotice();

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    await waitFor(() => expect(screen.queryByText('First paragraph.')).not.toBeInTheDocument());
    expect(screen.queryByText(EXAMPLE)).not.toBeInTheDocument();
  });

  test('mounting it again shows it again', async () => {
    const first = renderNotice();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByText('First paragraph.')).not.toBeInTheDocument());
    first.unmount();

    renderNotice();

    expect(screen.getByText('First paragraph.')).toBeInTheDocument();
  });

  test('closing it writes to no storage', async () => {
    const local = vi.spyOn(Storage.prototype, 'setItem');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject());
    renderNotice();

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByText('First paragraph.')).not.toBeInTheDocument());

    expect(local).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test('each notice is a landmark named after its field, so two on a page are told apart and none answers to the field’s own label', () => {
    render(
      <>
        <FieldNotice id="a" label="First field">
          One.
        </FieldNotice>
        <FieldNotice id="b" label="Second field">
          Two.
        </FieldNotice>
      </>
    );

    expect(screen.getByRole('region', { name: 'Notice: First field' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Notice: Second field' })).toBeInTheDocument();
  });

  test('has no accessibility violations', async () => {
    const { container } = renderNotice();
    expect(await axe(container)).toHaveNoViolations();
  });
});
