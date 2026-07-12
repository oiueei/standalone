import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import InfoPopover from './InfoPopover';

describe('InfoPopover', () => {
  test('the (i) button starts closed with no aria-controls, then opens on click', () => {
    render(
      <InfoPopover title="CSV format" id="panel-1">
        <p>body</p>
      </InfoPopover>
    );
    const button = screen.getByRole('button', { name: 'CSV format' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).not.toHaveAttribute('aria-controls');
    expect(screen.queryByText('body')).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(button).toHaveAttribute('aria-controls', 'panel-1');
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  test('the positioning class lives on the wrapper div, never on the HDS Notification', () => {
    render(
      <InfoPopover title="CSV format" id="panel-1">
        <p>body</p>
      </InfoPopover>
    );
    fireEvent.click(screen.getByRole('button', { name: 'CSV format' }));

    // This is the BulkInviteCsv bug this component fixes: HDS's Notification
    // root carries its own `position: relative` at the same selector
    // specificity as a single custom class, so a positioning class passed as
    // `className` to Notification is not reliably absolute. The wrapper we
    // own must carry it instead.
    const wrapper = document.getElementById('panel-1');
    expect(wrapper).toHaveClass('info-popover-panel');

    const notification = wrapper.querySelector('[class*="notification"]');
    expect(notification).not.toHaveClass('info-popover-panel');
  });

  test('closes on blur', () => {
    render(
      <InfoPopover title="CSV format" id="panel-1">
        <p>body</p>
      </InfoPopover>
    );
    const button = screen.getByRole('button', { name: 'CSV format' });
    fireEvent.click(button);
    expect(screen.getByText('body')).toBeInTheDocument();

    fireEvent.blur(button.closest('.info-popover'));
    expect(screen.queryByText('body')).not.toBeInTheDocument();
  });
});
