import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import i18n, { SUPPORTED_LANGUAGES } from '../i18n';
import { Button, Notification } from 'hds-react';
import useTheeeme from '../hooks/useTheeeme';
import PageLayout from '../components/PageLayout';
import { safeNextPath } from '../utils/nextPath';
import ButtonLink from '../components/ButtonLink';
import { collectionPath, collectionThingPath } from '../utils/collectionPath';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { errorKey, translateError } from '../utils/errorKey';

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  useDocumentTitle(t('titles.verify'));
  const [error, setError] = useState('');
  // Set when the refusal on screen is one the backend deliberately survives
  // (`retryable`): the link still works, so the error screen owes a different
  // way out than "ask whoever invited you for a new one".
  const [linkAlive, setLinkAlive] = useState(false);
  // Set when the refusal is the server saying this reader no longer runs the thing
  // the link decides (`no_longer_manages`): the link is not expired and nobody
  // invited them, so the invitation-flavoured help line has nothing to say.
  const [noLongerManages, setNoLongerManages] = useState(false);
  const [success, setSuccess] = useState('');
  const [title, setTitle] = useState('');
  // ACCOUNT_DELETE preview data — unlike a booking decision, account deletion
  // is never auto-committed from the load effect: the person must press the
  // explicit confirm button below.
  const [deletePreview, setDeletePreview] = useState(null);
  const [deleting, setDeleting] = useState(false);
  // Guards the auto-commit POST so React 19 StrictMode's double-invoked effect
  // (dev only) can't fire the irreversible booking decision twice.
  const committedRef = useRef(false);
  // The code this page has already asked the server about. A link is single-use, so
  // it is redeemed once per code whatever re-runs the effect below: the second GET
  // would find it spent and paint "invalid or expired" under a person who has just
  // signed in.
  const redeemedRef = useRef(null);
  const isLoggedIn = !!localStorage.getItem('userCode');

  const { btnStyle } = useTheeeme();

  useEffect(() => {
    if (redeemedRef.current === code) return undefined;
    redeemedRef.current = code;
    let settled = false;
    // Don't let a stalled network leave the user stuck on "Verifying…" forever:
    // after 15s with no response, fall through to the existing error screen.
    const timer = setTimeout(() => {
      if (!settled) setError(errorKey('common.connectionError'));
    }, 15000);
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.requires_confirmation && data.action === 'ACCOUNT_DELETE') {
          // Deleting an account is the one action even a real click must not
          // commit implicitly: show the preview (whose account, how much goes
          // with it) and wait for the explicit button below.
          setDeletePreview(data);
        } else if (res.ok && data.requires_confirmation) {
          // Booking accept/reject is irreversible, so the API only *previews* on a
          // bare GET — an email link-scanner must never decide a hold. The human's
          // single click was opening this link, so commit it now with a POST fired
          // from real JS: a scanner runs no JS and still can't auto-decide, while
          // the person needs no second click. The ref guards StrictMode's dev-only
          // double-invoke from firing the decision twice.
          if (!committedRef.current) {
            committedRef.current = true;
            const commit = await fetch(`/api/v1/auth/verify/${code}/`, {
              method: 'POST',
              credentials: 'include',
            });
            const done = await commit.json();
            if (commit.ok && done.action === 'BOOKING_ACCEPT') {
              setTitle(t('verify.confirmed'));
              setSuccess(t('verify.holdConfirmed'));
            } else if (commit.ok && done.action === 'BOOKING_REJECT') {
              setTitle(t('verify.rejected'));
              setSuccess(t('verify.holdRejected'));
            } else if (commit.ok && done.action === 'PROPOSAL_APPROVE') {
              // The owner chose which of the two links to open, so the click is
              // the decision — same as a booking. The scanner guard still holds:
              // the commit only runs from real JS.
              setTitle(t('verify.confirmed'));
              setSuccess(t('verify.proposalApproved', { email: done.email }));
            } else if (commit.ok && done.action === 'PROPOSAL_REJECT') {
              setTitle(t('verify.declined'));
              setSuccess(t('verify.proposalDeclined'));
            } else if (done.code === 'no_longer_manages') {
              // A co-curator demoted after the email: the server was right to
              // refuse, and "invalid or expired — ask whoever invited you" would
              // send them looking for an invitation that is not the problem.
              setNoLongerManages(true);
              setError(errorKey('verify.noLongerManages'));
            } else if (done.retryable) {
              // "Not now", not "never". An approval the deployment's daily
              // invitation cap or the group's member ceiling refuses leaves the
              // suggestion pending and both links alive on purpose — the owner
              // is meant to come back tomorrow. Every other refusal here
              // consumes its RSVP, so `invalidOrExpired` is right for them and
              // was flatly wrong for this one: it told the owner the link was
              // dead while it was still good, and nothing would bring them back.
              // The reason is the server's own sentence, the same one the
              // in-app approval shows (see ManageInvitesPage).
              setLinkAlive(true);
              setError(done.error || errorKey('verify.invalidOrExpired'));
            } else {
              setError(errorKey('verify.invalidOrExpired'));
            }
          }
        } else if (res.ok && data.action === 'COLLECTION_REJECT') {
          setTitle(t('verify.declined'));
          setSuccess(t('verify.invitationDeclined'));
        } else if (res.ok && data.user) {
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          // The account's saved language, taken from here (the palette is no longer
          // the account's: it is the app's, or the collection's): the app-wide effect that applies it (`App.jsx`) runs
          // once, when the app mounts, and opening a magic link mounts it *before*
          // there is a session — its `/auth/me/` answers 401 — so until a reload a
          // person with a saved language saw the browser's ("English"
          // saved, link opened on a phone, app in Spanish). A real preference, so a
          // proper `changeLanguage` that persists like the profile's own Select;
          // empty ("Automatic") or unknown leaves things alone. Awaited, so the page
          // they land on is painted in it, and never allowed to fail the login.
          const saved = data.user?.language;
          if (saved && SUPPORTED_LANGUAGES.some((l) => l.code === saved)) {
            await i18n.changeLanguage(saved).catch(() => {});
          }
          // The backend decides where to land (`landing`): the collection the
          // link was for (or the one real group they have), the page they were
          // heading for, else home. There is no "welcome" landing any more:
          // someone who comes in by an open door is answered like
          // anyone else, from the groups they actually have, so a landing this
          // page does not know falls through to home.
          const target = data.collection || data.invited_collection;
          if (data.landing === 'collection' && target) {
            // `data.thing` is set when the join came from a "Reserve" click on a
            // specific thing — land them back on it, ready to act.
            navigate(
              data.thing
                ? collectionThingPath(target, data.collection_kind, data.thing)
                : collectionPath(target, data.collection_kind)
            );
          } else if (data.landing === 'path' && safeNextPath(data.path)) {
            // The page the reader was heading for when their session ran out
            // (`next` on the login). The server already validated it; checked
            // again here because it is fed to the router, and one that does not
            // pass falls through to home rather than anywhere odd.
            navigate(data.path);
          } else {
            navigate('/');
          }
        } else {
          setError(errorKey('verify.invalidOrExpired'));
        }
      } catch {
        setError(errorKey('common.connectionError'));
      } finally {
        settled = true;
        clearTimeout(timer);
      }
    };
    verify();
    return () => clearTimeout(timer);
    // `t` is not a dependency, on purpose: a language change gives `useTranslation`
    // a new `t`, and this effect redeeming the link must not run again for it. A
    // magic link is single-use, so a second run would find it spent and show an
    // error to someone who has just signed in — and the sign-in itself now changes
    // the language (the account's saved one), and so does `App.jsx`'s own effect on
    // a visitor who already had a session. Nothing here is translated after a
    // language could have changed except the failure messages, which read `t` as
    // it was when the link was opened.
    // `navigate` is not one either: it changes identity with every address, and the
    // sign-in navigates away while the next page's chunk loads and this one is still
    // mounted. The effect redeems the link once per `code` (`redeemedRef`).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  // Both the success and error heroes offer the same way out.
  const exitAction = (
    <ButtonLink to={isLoggedIn ? '/' : '/login'} style={btnStyle}>
      {isLoggedIn ? t('verify.goToHomepage') : t('verify.goToLogin')}
    </ButtonLink>
  );

  const handleAccountDelete = async () => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/v1/auth/verify/${code}/`, {
        method: 'POST',
        credentials: 'include',
      });
      const done = await res.json();
      if (res.ok && done.action === 'ACCOUNT_DELETE') {
        // The account is gone — so is everything this browser knew about it.
        localStorage.removeItem('userCode');
        setDeletePreview(null);
        setTitle(t('verify.accountDeletedTitle'));
        setSuccess(t('verify.accountDeletedBody'));
      } else {
        setDeletePreview(null);
        setError(errorKey('verify.invalidOrExpired'));
      }
    } catch {
      setError(errorKey('common.connectionError'));
    } finally {
      setDeleting(false);
    }
  };

  if (deletePreview && !success && !error) {
    return (
      <PageLayout title={t('verify.accountDeleteTitle')}>
        <p>
          {t('verify.accountDeleteSummary', {
            email: deletePreview.email,
            collections: deletePreview.collections,
            things: deletePreview.things,
          })}
        </p>
        <p className="section-mt">{t('deleteAccount.whatStays')}</p>
        <div
          className="section-mt"
          style={{ display: 'flex', gap: 'var(--spacing-s)', flexWrap: 'wrap' }}
        >
          <Button variant="danger" disabled={deleting} onClick={handleAccountDelete}>
            {deleting ? t('verify.accountDeleting') : t('verify.accountDeleteConfirm')}
          </Button>
          <ButtonLink to={isLoggedIn ? '/' : '/login'}>{t('common.cancel')}</ButtonLink>
        </div>
      </PageLayout>
    );
  }

  if (success) {
    return (
      <PageLayout title={title} heroActions={exitAction}>
        <Notification label={t('common.done')} type="success">
          {success}
        </Notification>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title={t('verify.oops')} heroActions={exitAction}>
        <Notification label={t('common.error')} type="error">
          {translateError(t, error)}
        </Notification>
        {!noLongerManages && (
          <p className="section-mt">{t(linkAlive ? 'verify.refusalHelp' : 'verify.expiredHelp')}</p>
        )}
      </PageLayout>
    );
  }

  return <PageLayout title={t('verify.verifying')} />;
}
