import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect } from 'vitest';
import CollectionLinkbox from './CollectionLinkbox';

const collection = {
  code: 'COL001',
  headline: 'Kitchen Collection',
  thumbnail_url: 'https://res.cloudinary.com/demo/image/upload/oiueei/collections/cover.jpg',
  things: [{ code: 'THG001' }, { code: 'THG002' }],
  invites: [{ code: 'INV001' }],
};

describe('CollectionLinkbox', () => {
  test('renders no thumbnail, even when the collection has one (S8: full-width rows, no image)', () => {
    const { container } = render(
      <MemoryRouter>
        <CollectionLinkbox collection={collection} showInfo />
      </MemoryRouter>
    );
    expect(container.querySelector('img')).toBeNull();
  });

  test('still exposes the headline, counts, and a link to the collection', () => {
    render(
      <MemoryRouter>
        <CollectionLinkbox collection={collection} showInfo />
      </MemoryRouter>
    );
    expect(screen.getByText('Kitchen Collection')).toBeInTheDocument();
    expect(screen.getByText(/2.*·.*1/)).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/collections/COL001');
  });
});
