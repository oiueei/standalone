import { useTranslation } from 'react-i18next';
import { IconCheck } from 'hds-react';

export default function TheeemeSelector({ theeemes, value, onChange }) {
  const { t } = useTranslation();

  if (!theeemes || theeemes.length === 0) return null;

  return (
    <div className="theeeme-selector">
      <span className="theeeme-selector-label">{t('editProfile.theeemeLabel')}</span>
      <div className="theeeme-selector-grid">
        {theeemes.map((th) => {
          const selected = th.code === value;
          return (
            <button
              key={th.code}
              type="button"
              className={`theeeme-option${selected ? ' theeeme-option--selected' : ''}`}
              onClick={() => onChange(th.code)}
              aria-pressed={selected}
              aria-label={th.name}
            >
              <span className="theeeme-swatches">
                <span className="theeeme-swatch" style={{ backgroundColor: `var(--color-${th.color_01})` }} />
                <span className="theeeme-swatch" style={{ backgroundColor: `var(--color-${th.color_02})` }} />
                <span className="theeeme-swatch" style={{ backgroundColor: `var(--color-${th.color_03})` }} />
              </span>
              <span className="theeeme-name">{th.name}</span>
              {selected && (
                <span className="theeeme-check">
                  <IconCheck size="xs" />
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
