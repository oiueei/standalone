import { useState } from 'react';

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
      <button
        aria-label={tooltip}
        onClick={onClick}
        disabled={disabled}
        style={{
          background: 'none',
          border: 'none',
          cursor: disabled ? 'default' : 'pointer',
          padding: 'var(--spacing-xs)',
          // WCAG 2.5.5 / mobile-first: keep the tap target at least 44×44.
          minWidth: '44px',
          minHeight: '44px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: disabled ? 'var(--color-black-40)' : 'var(--color-black-90)',
        }}
      >
        {children}
      </button>
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
          whiteSpace: 'nowrap',
          zIndex: 1000,
          pointerEvents: 'none',
        }}>
          {tooltip}
        </div>
      )}
    </div>
  );
}
