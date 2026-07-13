import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import ThingTags from './ThingTags';

const thing = { type: 'GIFT_THING', status: 'ACTIVE', tags: ['Vintage'] };

describe('ThingTags', () => {
  test('shows the thing type and its owner-defined tags', () => {
    render(<ThingTags thing={thing} isOwner={false} />);
    expect(screen.getByText('Vintage')).toBeInTheDocument();
  });

  test('a tag written once per language reads as a word, not as raw JSON (O6)', () => {
    // The raw string stays the value — it is what the collection vocabulary and
    // the subset check compare — so only the chip resolves. (Test i18n is English.)
    const label = '{"es": "Juguetes", "ca": "Joguines", "en": "Toys"}';
    render(<ThingTags thing={{ ...thing, tags: [label] }} isOwner={false} />);

    expect(screen.getByText('Toys')).toBeInTheDocument();
    expect(screen.queryByText(/\{"es"/)).toBeNull();
  });
});
