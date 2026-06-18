import { useTranslation } from 'react-i18next';

/**
 * Owner-only list of a thing's future bookings (pending + confirmed), shared by
 * ThingPage and ThingLinkbox. The active pending booking is bold and starred with
 * `*` when more than one pending booking exists. Renders nothing unless the viewer
 * is the owner and there is at least one booking.
 */
export default function OwnerBookingsList({ bookings, activePendingCode, isOwner }) {
  const { t, i18n } = useTranslation();
  if (!isOwner || bookings.length === 0) return null;

  const pendingCount = bookings.filter((b) => b.status === 'PENDING').length;
  return (
    <ul className="thing-card-bookings">
      {bookings.map((b) => {
        const isActive = isOwner && b.code === activePendingCode;
        const showStar = isActive && pendingCount > 1;
        return (
          <li key={b.code} style={{ fontWeight: isActive ? 'bold' : 'normal' }}>
            {isOwner && b.requester_name && <>{b.requester_name}. </>}
            {b.created && <>{new Date(b.created).toLocaleDateString(i18n.language, { day: 'numeric', month: 'short' })}. </>}
            {b.start_date && b.end_date && (
              <>{new Date(b.start_date).toLocaleDateString(i18n.language)} – {new Date(b.end_date).toLocaleDateString(i18n.language)}</>
            )}
            {b.delivery_date && <>{new Date(b.delivery_date).toLocaleDateString(i18n.language)}, {t('thingCard.qty')} {b.quantity}</>}
            {b.offered_thing_headlines && b.offered_thing_headlines.length > 0 && (
              <><br />{t('swap.offeredItems')}: {b.offered_thing_headlines.join(', ')}</>
            )}
            {' '}
            <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
              ({b.status === 'ACCEPTED' ? t('thingCard.confirmed') : t('thingCard.pending')}){showStar ? ' *' : ''}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
