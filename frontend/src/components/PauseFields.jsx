import { DateInput, Notification, ToggleButton } from 'hds-react';
import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import useTheeeme from '../hooks/useTheeeme';
import { DISPLAY_DATE_FORMAT, displayToIso } from '../utils/rental';
import { bookingsInPause } from '../utils/pause';
import hdsLang from '../utils/hdsLang';
import StatusRegion from './StatusRegion';

/**
 * Pausing a thing with a calendar between two days, both included: between them nobody
 * can request or book it, and bookings already made are not cancelled. One switch (its
 * label is the title and the explanation together) and, when on, the two days. Off, the
 * page sends both days empty.
 *
 * Before saving it says how many of the thing's bookings fall in those days, so that
 * whoever pauses it knows they are not cancelled and where to deal with them ("Requests to me":
 * a reservation can be cancelled there, a loan only declined while pending): the same strict
 * overlap the server uses, worked out on the list a manager already receives.
 *
 * Controlled; the dates are the display strings of the date inputs and `errors` holds
 * what the server said about each day. `idPrefix` is `edit-thing`.
 */
export default function PauseFields({
  idPrefix,
  enabled,
  setEnabled,
  from,
  setFrom,
  until,
  setUntil,
  errors = {},
  bookings = [],
  isReservation = false,
}) {
  const { t, i18n } = useTranslation();
  const { toggleTheme } = useTheeeme();
  // Only shown inside the block below, which exists while the pause is on.
  const count = bookingsInPause(bookings, displayToIso(from), displayToIso(until));

  const dateProps = {
    dateFormat: DISPLAY_DATE_FORMAT,
    language: hdsLang(i18n.language),
    openButtonAriaLabel: t('datePicker.open'),
    selectButtonLabel: t('datePicker.select'),
    closeButtonLabel: t('datePicker.close'),
    malformedDateErrorText: t('thingPause.malformedDate'),
  };

  return (
    <>
      <ToggleButton
        id={`${idPrefix}-pause`}
        variant="inline"
        label={t('thingPause.toggleLabel')}
        checked={enabled}
        onChange={(val) => setEnabled(!val)}
        theme={toggleTheme}
      />
      {enabled && (
        <>
          <DateInput
            id={`${idPrefix}-paused-from`}
            label={t('thingPause.fromLabel')}
            value={from}
            onChange={(value) => setFrom(value)}
            required
            invalid={!!errors.from}
            errorText={errors.from}
            {...dateProps}
          />
          <DateInput
            id={`${idPrefix}-paused-until`}
            label={t('thingPause.untilLabel')}
            value={until}
            onChange={(value) => setUntil(value)}
            required
            invalid={!!errors.until}
            errorText={errors.until}
            {...dateProps}
          />
          <StatusRegion>
            {count > 0 && (
              <Notification type="alert" size="small">
                <Trans
                  i18nKey={isReservation ? 'thingPause.bookingsInRange' : 'thingPause.loansInRange'}
                  count={count}
                  components={[<span key="0" />, <Link key="1" to="/owner-bookings" />]}
                />
              </Notification>
            )}
          </StatusRegion>
        </>
      )}
    </>
  );
}
