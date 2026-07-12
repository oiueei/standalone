import { useState } from 'react';
import { Notification, IconInfoCircleFill } from 'hds-react';

/**
 * (i) icon button that reveals an info panel on hover/focus/click, closing on
 * mouse-leave/blur. The positioning class (`.info-popover-panel`, in App.css)
 * lives on the wrapper `<div>` below — never pass a positioning class as
 * `className` to the HDS `Notification` itself. Its rendered root carries
 * HDS's own `position: relative` at the same selector specificity as a
 * single custom class, so which one wins depends on unpredictable
 * style-injection order (this was BulkInviteCsv's original bug: the panel
 * sometimes rendered in flow instead of absolutely positioned).
 *
 * Props:
 *   title – panel label (also the button's accessible name)
 *   children – panel body
 *   id – id for the panel wrapper, referenced by aria-controls while open
 */
export default function InfoPopover({ title, children, id }) {
  const [open, setOpen] = useState(false);

  return (
    <span
      className="info-popover"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <button
        type="button"
        className="info-popover-button"
        aria-label={title}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        <IconInfoCircleFill aria-hidden="true" />
      </button>
      {open && (
        <div id={id} className="info-popover-panel">
          <Notification type="info" size="small" label={title}>
            {children}
          </Notification>
        </div>
      )}
    </span>
  );
}
