import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import TagInput from './TagInput';

// TagInput defines the collection's tag vocabulary — what it hands to onChange
// is what the backend stores and what a thing's tags are validated against.

function renderInput(props = {}) {
  const onChange = vi.fn();
  render(<TagInput tags={[]} onChange={onChange} label="Tags" {...props} />);
  return onChange;
}

const typeAndAdd = (value) => {
  fireEvent.change(screen.getByLabelText('Tags'), { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
};

describe('TagInput (the tag vocabulary editor)', () => {
  test('adding a label trims it and clears the input', () => {
    const onChange = renderInput();

    typeAndAdd('  Juguetes  ');

    expect(onChange).toHaveBeenCalledWith(['Juguetes']);
    expect(screen.getByLabelText('Tags')).toHaveValue('');
  });

  test('Enter adds the label without submitting anything', () => {
    const onChange = renderInput();

    fireEvent.change(screen.getByLabelText('Tags'), { target: { value: 'Herramientas' } });
    fireEvent.keyDown(screen.getByLabelText('Tags'), { key: 'Enter' });

    expect(onChange).toHaveBeenCalledWith(['Herramientas']);
  });

  test('a duplicate differing only in case is silently dropped', () => {
    const onChange = renderInput({ tags: ['Juguetes'] });

    typeAndAdd('JUGUETES');

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Tags')).toHaveValue('');
  });

  test('a plain label over 32 characters is refused inline', () => {
    const onChange = renderInput();

    typeAndAdd('x'.repeat(33));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/over 32 characters/)).toBeInTheDocument();
  });

  test('a localized map gets 32 per language — and the RAW string stays the value', () => {
    const onChange = renderInput();
    const map = '{"es": "Juguetes", "ca": "Joguines"}';

    typeAndAdd(map);

    // The raw JSON (44 chars) is longer than 32 — the limit must apply per
    // language, not to the serialized string.
    expect(onChange).toHaveBeenCalledWith([map]);
  });

  test('a localized chip shows words, names its languages, and one long language is refused', () => {
    const onChange = renderInput({ tags: ['{"es": "Juguetes", "ca": "Joguines"}'] });

    // The chip resolves to a reader word, never raw JSON; the tooltip names
    // the languages so the owner can tell the two kinds apart.
    expect(screen.getByText('Juguetes')).toBeInTheDocument();
    expect(screen.queryByText(/"es"/)).not.toBeInTheDocument();
    expect(screen.getByTitle('es · ca')).toBeInTheDocument();

    typeAndAdd(`{"es": "corto", "ca": "${'x'.repeat(33)}"}`);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/over 32 characters/)).toBeInTheDocument();
  });

  test('at the cap of 12 the input and Add are disabled', () => {
    renderInput({ tags: Array.from({ length: 12 }, (_, i) => `tag-${i}`) });

    expect(screen.getByLabelText('Tags')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled();
  });
});
