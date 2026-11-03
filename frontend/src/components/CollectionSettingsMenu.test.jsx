import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, test, expect } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import CollectionSettingsMenu from './CollectionSettingsMenu';

expect.extend(toHaveNoViolations);

const renderMenu = (kind = 'STALL') =>
  render(
    <MemoryRouter>
      <CollectionSettingsMenu code="COL001" kind={kind} />
    </MemoryRouter>
  );

describe('CollectionSettingsMenu', () => {
  test('is a closed cogwheel button named Settings', () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: 'Settings' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).not.toHaveAttribute('aria-controls');
    expect(screen.queryByRole('link')).toBeNull();
  });

  test('opens a plain panel with the Appearance link, at the address of its kind', () => {
    const { container } = renderMenu('LIBRARY');
    const trigger = screen.getByRole('button', { name: 'Settings' });

    fireEvent.click(trigger);

    const panel = container.querySelector('#collection-settings-menu-panel');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(trigger).toHaveAttribute('aria-controls', panel.id);
    expect(panel.getAttribute('role')).toBeNull();
    expect(panel.getAttribute('aria-label')).toBeNull();
    expect(screen.getByRole('link', { name: 'Appearance' })).toHaveAttribute(
      'href',
      '/library/COL001/settings/appearance'
    );
  });

  test('offers the pages that exist: Appearance and Notifications, no Availability yet', () => {
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

    expect(screen.getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual([
      '/stall/COL001/settings/appearance',
      '/stall/COL001/settings/notifications',
    ]);
  });

  test('Escape closes it and returns the focus to the trigger', () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: 'Settings' });
    fireEvent.click(trigger);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(screen.queryByRole('link')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  test('following the link closes the panel', () => {
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

    fireEvent.click(screen.getByRole('link', { name: 'Appearance' }));

    expect(screen.queryByRole('link')).toBeNull();
  });

  test('has no accessibility violations, closed or open', async () => {
    const { container } = renderMenu();
    expect(await axe(container)).toHaveNoViolations();
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
