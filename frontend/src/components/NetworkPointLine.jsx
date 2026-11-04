import { IconLocation } from 'hds-react';
import { useTranslation } from 'react-i18next';
import useTheeeme from '../hooks/useTheeeme';

/**
 * "Lent by {name}", then where and when it is collected, from the pickup point the
 * server resolved for its owner (`thing.network_point`: `display_name` is the
 * entity's name, else the dinamizador's own, decided once on the server for every
 * place that names it). A quiet box with a pin, because it is what a person needs
 * to go and collect the thing; it is not interactive (no link, no landmark).
 * Nothing for a thing outside a network (`network_point` is null). The address and
 * hours are shown as written, never as links; React escapes them.
 */
export default function NetworkPointLine({ point }) {
  const { t } = useTranslation();
  const { tc } = useTheeeme();
  if (!point) return null;
  return (
    <div
      className="network-point"
      data-testid="network-point-line"
      // The frame is the colour of the hero (the koro's band), so it belongs to the palette in force.
      style={tc.color_03 ? { borderColor: `var(--color-${tc.color_03})` } : undefined}
    >
      <IconLocation aria-hidden="true" className="network-point-icon" />
      <div className="network-point-text">
        <strong>
          {t('networkPoint.lentBy', { name: point.display_name || t('common.aMember') })}
        </strong>{' '}
        {point.address && <span className="network-point-detail">{point.address}</span>}{' '}
        {point.hours_note && <span className="network-point-detail">{point.hours_note}</span>}
      </div>
    </div>
  );
}
