import { useEffect, useState } from 'react';
import { Button } from 'hds-react';

/**
 * An icon-only HDS action Button that reveals its label on hover/focus.
 *
 * Not an HDS `Tooltip`: that component renders its own fixed IconQuestionCircle
 * trigger and takes the panel content as `children`, so it cannot host an
 * action. Our two callers (MyBookingsPage's cancel, ManageInvitesPage's
 * resend/remove) are action buttons inside `Table` cells, where the bubble is
 * the visible label for an icon. The Button itself is HDS; only the bubble is
 * ours (it takes the look of HDS's small Tooltip placed on top), and it satisfies the three WCAG 1.4.13 conditions for content shown on
 * hover or focus:
 *
 *  - dismissible — Escape hides it without moving focus;
 *  - hoverable   — no `pointer-events: none`, and a transparent bridge fills the
 *                  gap to the button, so the pointer may travel onto it (it sits
 *                  above the button, which is the direction a pointer drifts
 *                  when reading);
 *  - persistent  — it stays until blur, mouse-leave or Escape; nothing times out.
 *
 * The bubble is `aria-hidden`: it repeats the button's own `aria-label`
 * verbatim, so exposing it again would announce the label twice.
 */
export default function TooltipButton({ tooltip, onClick, disabled, children }) {
  const [visible, setVisible] = useState(false);
  // Escape re-shows on the next hover/focus, so a dismissal is never sticky.
  const [dismissed, setDismissed] = useState(false);

  const show = () => {
    setDismissed(false);
    setVisible(true);
  };
  const hide = () => setVisible(false);

  // WCAG 1.4.13 "dismissible": Escape hides the bubble without moving the
  // pointer or the focus, so it can never trap a row's content underneath it.
  // The listener is on `document`, not on the wrapper: a mouse user hovering the
  // button usually has focus somewhere else entirely, so a wrapper-level handler
  // would only ever fire for the keyboard case. Attached only while the bubble
  // is up, and it does not stop propagation — an ancestor dialog still gets its
  // own Escape.
  useEffect(() => {
    if (!visible || dismissed) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setDismissed(true);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [visible, dismissed]);

  return (
    // The div is a passive wrapper, not an interactive target: the real
    // Button below carries all the keyboard/aria semantics, and its own
    // focus/blur bubble up here to control the bubble's visibility.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      className="tooltip-button"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <Button
        variant="supplementary"
        size="small"
        iconStart={children}
        aria-label={tooltip}
        onClick={onClick}
        disabled={disabled}
        // WCAG 2.5.5 / mobile-first: size="small" keeps the tap target at
        // least 44×44 (--min-size). DESIGN §11: black icon, black-40 disabled.
        style={{ '--color': 'var(--color-black-90)', '--color-disabled': 'var(--color-black-40)' }}
      />
      {visible && !dismissed && !disabled && (
        <div className="tooltip-button-bubble" aria-hidden="true">
          {tooltip}
        </div>
      )}
    </div>
  );
}
