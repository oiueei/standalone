import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import useTheeeme from '../../hooks/useTheeeme';
import { loadMeProfile } from '../../hooks/useCapabilities';
import { profileIncomplete } from '../../utils/profile';
import ButtonLink from '../ButtonLink';

/** What the request page says once the request has gone, and the way back. */
export default function RequestSuccess({
  isReservation,
  headline,
  bookedWhen,
  joinedGroup,
  backPath,
  backLabel,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  // Someone who arrived by a magic link has no name and no demographics: the one moment
  // they have just done something here is the kind one to ask. Nothing is shown until
  // `/auth/me/` has answered, and nothing if it never does.
  const [incomplete, setIncomplete] = useState(false);
  useEffect(() => {
    let live = true;
    loadMeProfile().then((me) => {
      if (live) setIncomplete(profileIncomplete(me));
    });
    return () => {
      live = false;
    };
  }, []);

  return (
    <>
      <Notification
        autofocus
        label={isReservation ? t('reservation.successLabel') : t('request.successLabel')}
        type="success"
      >
        {isReservation ? t('reservation.successMessage') : t('request.successMessage')}
        {/* What and when, said back: a reservation confirms on the spot,
            with no owner step to catch a wrong day or hour. */}
        {bookedWhen && (
          <p style={{ margin: 'var(--spacing-2-xs) 0 0' }}>
            <strong>{headline}</strong>
            <br />
            {bookedWhen}
          </p>
        )}
        {joinedGroup && (
          <p style={{ margin: 'var(--spacing-2-xs) 0 0' }}>
            {t(isReservation ? 'reservation.joinedGroup' : 'request.joinedGroup', {
              group: joinedGroup,
            })}
          </p>
        )}
      </Notification>
      <div className="spacer-m" />
      {incomplete ? (
        // A column of two buttons across the whole width at every width, like the request
        // button of the form above (a `.button-row-wide` would leave them in a row, as wide as
        // their text, from 768px).
        <div className="button-col">
          <ButtonLink to="/me/edit" state={{ backPath, backLabel }} style={btnStyle} fullWidth>
            {t('request.completeProfile')}
          </ButtonLink>
          <Button
            variant="secondary"
            fullWidth
            onClick={() => navigate(backPath)}
            style={btnSecondaryStyle}
          >
            {t('request.backTo', { label: backLabel })}
          </Button>
        </div>
      ) : (
        <Button
          variant="secondary"
          fullWidth
          onClick={() => navigate(backPath)}
          style={btnSecondaryStyle}
        >
          {t('request.backTo', { label: backLabel })}
        </Button>
      )}
    </>
  );
}
