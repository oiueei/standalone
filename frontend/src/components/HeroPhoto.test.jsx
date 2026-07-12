import { render } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import HeroPhoto from './HeroPhoto';

describe('HeroPhoto', () => {
  test('the photo keeps its alt text and the decorative wedge stays aria-hidden', () => {
    const { container } = render(
      <HeroPhoto photoUrl="https://example.com/photo.jpg" alt="Lala" koroType="basic" color03="copper" />
    );

    const img = container.querySelector('img.hero-photo');
    expect(img).toHaveAttribute('alt', 'Lala');
    expect(img).toHaveAttribute('src', 'https://example.com/photo.jpg');

    const wedge = container.querySelector('.hero-photo-diag');
    expect(wedge).toHaveAttribute('aria-hidden', 'true');
  });

  test('renders the mobile-only wave (hidden on desktop by App.css, not by React)', () => {
    // The wave must exist in the DOM at every width — App.css's base rule
    // (`.hero-photo-top-koros { display: none }`) hides it on desktop, and the
    // `max-width: 767px` query is what shows it, not conditional rendering.
    const { container } = render(
      <HeroPhoto photoUrl="https://example.com/photo.jpg" alt="Lala" koroType="basic" color03="copper" />
    );
    expect(container.querySelector('.hero-photo-top-koros')).toBeTruthy();
  });
});
