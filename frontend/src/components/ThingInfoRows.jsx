import { useTranslation } from 'react-i18next';
import { IconTicket, IconEuroSign, IconCalendar, IconLocation, IconShield } from 'hds-react';

/**
 * The `thing-card-info` rows shared by ThingPage and ThingLinkbox: type, fee,
 * availability (live for date-based types, the static enum hint otherwise),
 * location and condition. Extra rows specific to a view (e.g. answer/transfer
 * counts on ThingLinkbox) are passed as `children` and rendered after the core
 * rows inside the same container.
 */
export default function ThingInfoRows({ thing, isDateBased, children }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="thing-card-info">
      <div className="thing-card-info-row">
        <IconTicket size="m" aria-hidden="true" />
        <span className="thing-card-info-label">{t('thingPage.typeLabel')}</span>
        <span>{t('types.' + thing.type)}</span>
      </div>
      {thing.fee && (
        <div className="thing-card-info-row">
          <IconEuroSign size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.priceLabel')}</span>
          <span>{thing.fee} €</span>
        </div>
      )}
      {/* Live availability (date-based things): computed from the booking calendar */}
      {isDateBased && (
        <div className="thing-card-info-row">
          <IconCalendar size="m" aria-hidden="true" />
          <span className="thing-card-info-label">{t('thingPage.availabilityLabel')}</span>
          <span>
            {thing.available_today
              ? t('availability.IMMEDIATE')
              : thing.next_available
                ? t('availability.nextAvailable', { date: new Date(thing.next_available).toLocaleDateString(i18n.language, { day: 'numeric', month: 'numeric' }) })
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
