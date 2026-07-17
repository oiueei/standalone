import { useState } from 'react';
import { Button } from 'hds-react';

export default function TooltipButton({ tooltip, onClick, disabled, children }) {
  const [visible, setVisible] = useState(false);

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
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
      {visible && !disabled && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 4px)',
          right: 0,
          backgroundColor: 'var(--color-black-90)',
          color: 'var(--color-white)',
          padding: '4px 8px',
          borderRadius: '2px',
          fontSize: 'var(--fontsize-body-s)',
          maxWidth: 'min(280px, 80vw)',
          zIndex: 1000,
          pointerEvents: 'none',
        }}>
          {tooltip}
        </div>
      )}
    </div>
  );
}
