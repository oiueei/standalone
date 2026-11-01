import { Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';
import StatusRegion from './StatusRegion';

const REASON_KEY = {
  invalid: 'bulkInvite.reasonInvalid',
  duplicate: 'bulkInvite.reasonDuplicate',
  already_member: 'bulkInvite.reasonAlreadyMember',
  already_invited: 'bulkInvite.reasonAlreadyInvited',
  already_asked: 'bulkInvite.reasonAlreadyAsked',
  daily_limit: 'bulkInvite.reasonDailyLimit',
};

/**
 * The summary of a batch of invitations — how many went out, and which were skipped and
 * why — as `POST /collections/{code}/invite/bulk/` answers it (`{invited, skipped:
 * [{email, reason}]}`). Shared by the two ways of sending a batch: the CSV tool
 * (`BulkInviteCsv`) and the invitations field of `/invites` when it holds several
 * addresses, so both say it in the same words and the same shape.
 *
 * It is a live region that is always rendered, with the notification inside it only when
 * there is a `result` (`StatusRegion`: a region added together with its content announces
 * nothing). A reason it does not know reads as `invalid`.
 */
export default function BulkInviteResult({ result }) {
  const { t } = useTranslation();
  return (
    <StatusRegion>
      {result && (
        <Notification
          type={result.invited > 0 ? 'success' : 'info'}
          size="small"
          style={{ marginTop: 'var(--spacing-s)' }}
        >
          {t('bulkInvite.resultInvited', { count: result.invited })}
          {result.skipped && result.skipped.length > 0 && (
            <>
              <div style={{ marginTop: 'var(--spacing-2-xs)' }}>
                {t('bulkInvite.resultSkipped', { count: result.skipped.length })}
              </div>
              <ul style={{ margin: 'var(--spacing-2-xs) 0 0', paddingLeft: 'var(--spacing-m)' }}>
                {result.skipped.map((s, i) => (
                  <li key={i}>
                    {s.email} — {t(REASON_KEY[s.reason] || 'bulkInvite.reasonInvalid')}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Notification>
      )}
    </StatusRegion>
  );
}
