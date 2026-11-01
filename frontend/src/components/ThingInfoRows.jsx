import { useTranslation } from 'react-i18next';
import {
  IconTicket,
  IconEuroSign,
  IconLock,
  IconCalendar,
  IconLocation,
  IconShield,
} from 'hds-react';
import { formatDate } from '../utils/rental';
import { hasAmount } from '../constants/things';
import DepositPolicy from './DepositPolicy';

/**
 * The `thing-card-info` rows shared by ThingPage and ThingLinkbox: type, fee,
 * availability (live for date-based types, the static enum hint otherwise),
 * location and condition. Extra rows specific to a view (e.g. answer/transfer
 * counts on ThingLinkbox) are passed as `children` and rendered after the core
 * rows inside the same container; `lead` is a row a view opens with (ThingPage's pickup
 * point), which the card does not carry.
 */
export default function ThingInfoRows({ thing, isDateBased, hideType = false, lead, children }) {
  const { t } = useTranslation();
  return (
    <div className="thing-card-info">
      {lead}
      {/* Type row — hidden when the collection allows only one thing type (redundant). */}
      {!hideType && (
        <div className="thing-card-info-row">
          <IconTicket size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.typeLabel')}</span>
          <span>{t('types.' + thing.type)}</span>
        </div>
      )}
      {hasAmount(thing.fee) && (
        <div className="thing-card-info-row">
          <IconEuroSign size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.priceLabel')}</span>
          <span>{thing.fee} €</span>
        </div>
      )}
      {/* A distinct icon and a qualifying word, on purpose: a RENT thing shows
          both a price and a deposit, and without something to tell them apart
          "10 €" next to "50 €" reads as one 60 € cost instead of a rental fee
          plus a guarantee that comes back. */}
      {hasAmount(thing.deposit) && (
        <div className="thing-card-info-row">
          <IconLock size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.depositLabel')}</span>
          <span>
            {thing.deposit} € {t('thingPage.depositRefundableNote')}
          </span>
        </div>
      )}
      <DepositPolicy thing={thing} />
      {/* Live availability (date-based things): computed from the booking calendar */}
      {isDateBased && (
        <div className="thing-card-info-row">
          <IconCalendar size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.availabilityLabel')}</span>
          <span>
            {thing.available_today
              ? t('availability.IMMEDIATE')
              : thing.next_available
                ? t('availability.nextAvailable', {
                    date: formatDate(thing.next_available),
                  })
                : t('availability.noneSoon')}
          </span>
        </div>
      )}
      {/* Static availability hint (non-date types only) */}
      {!isDateBased && thing.availability && (
        <div className="thing-card-info-row">
          <IconCalendar size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.availabilityLabel')}</span>
          <span>{t('availability.' + thing.availability)}</span>
        </div>
      )}
      {thing.location && (
        <div className="thing-card-info-row">
          <IconLocation size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.locationLabel')}</span>
          <span>{thing.location}</span>
        </div>
      )}
      {thing.condition && (
        <div className="thing-card-info-row">
          <IconShield size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.conditionLabel')}</span>
          <span>{t('condition.' + thing.condition)}</span>
        </div>
      )}
      {children}
    </div>
  );
}
