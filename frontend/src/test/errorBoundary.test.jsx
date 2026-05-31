import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import ErrorBoundary from '../components/ErrorBoundary';

function Boom() {
  throw new Error('boom');
}

describe('ErrorBoundary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
  });

  test('renders a recoverable fallback when a child throws', () => {
    // React logs caught errors to console.error — silence the expected noise.
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go home' })).toBeInTheDocument();
  });
});
