import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect } from 'vitest';
import LoginPage from './LoginPage';

describe('LoginPage hero title-logo (S9)', () => {
  test('the h1 keeps the accessible name "OIUEEI" even though the logo replaces the text', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    // The logo is a decorative masked <span>, not text — aria-label on the h1
    // is what actually carries the accessible name here.
    const heading = screen.getByRole('heading', { name: 'OIUEEI' });
    expect(heading.tagName).toBe('H1');
    expect(heading).toHaveTextContent('');
  });

  test('the hero suppresses the 40px watermark so there is never a double logo', () => {
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    expect(container.querySelector('.form-hero')).toHaveClass('form-hero--no-watermark');
  });
});
