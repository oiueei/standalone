import { useTranslation } from 'react-i18next';
import { Koros, IconCheck } from 'hds-react';

const KORO_TYPES = ['basic', 'beat', 'calm', 'pulse', 'vibration', 'wave'];

export default function KoroSelector({ value, onChange }) {
  const { t } = useTranslation();

  return (
    <div className="koro-selector">
      <span id="koro-selector-label" className="koro-selector-label">{t('editProfile.koroLabel')}</span>
      <div className="koro-selector-grid" role="group" aria-labelledby="koro-selector-label">
        {KORO_TYPES.map((type) => {
          const selected = type === value;
          return (
            <button
              key={type}
              type="button"
              className={`koro-option${selected ? ' koro-option--selected' : ''}`}
              onClick={() => onChange(type)}
              aria-pressed={selected}
              aria-label={t('koro.' + type)}
            >
              <span className="koro-preview">
                <Koros type={type} style={{ fill: 'var(--color-white)' }} />
              </span>
              <span className="koro-name">{t('koro.' + type)}</span>
              {selected && (
                <span className="koro-check">
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
