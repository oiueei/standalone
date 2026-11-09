import { lazy, Suspense, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Button,
  IconArrowRedo,
  IconCamera,
  IconCopy,
  IconCrossCircle,
  IconEnvelope,
  IconShare,
  IconWhatsapp,
  LoadingSpinner,
} from 'hds-react';
import ThemedDialog from './ThemedDialog';
import useTheeeme from '../hooks/useTheeeme';
import useDismissable from '../hooks/useDismissable';
import { apiFetch } from '../services/api';
import Toast from './Toast';
import useShareLink from '../hooks/useShareLink';

// qrcode.react only renders once the owner opens the QR dialog — split it
// out of the CollectionPage chunk instead of shipping it to every visitor.
const QRCodeSVG = lazy(() => import('qrcode.react').then((m) => ({ default: m.QRCodeSVG })));

/**
 * Share menu for the CollectionPage hero: a curator's, and any member's in a
 * PUBLIC group (a PUBLIC group is shared by its own address — no token, nothing
 * to rotate or revoke — so a member holds no credential a curator would have to
 * pull back). The draft email carries no signature and no name: it opens in the
 * *sender's* mail client, which already says who is writing, so the same text is
 * right for the founder, a co-curator and a member.
 *
 * Presents as a single discreet `IconShare` in the hero's top-right, the last of
 * the corner's controls: a plain disclosure, the same gesture as `AccountMenu`
 * and `CollectionMenu` — a `<button aria-expanded aria-controls>` that shows a
 * panel of buttons, closed by Escape (focus back on the trigger), a click outside
 * (`useDismissable`) and focus moving out of the menu. It was an HDS `Select`
 * dressed as an icon, which a screen reader announces as a combobox; HDS v6 has no
 * menu. Every entry is a `<button>`, not a link: they are actions that first need
 * the link to share, which for a PRIVATE collection is minted on demand.
 *
 * PRIVATE collections use a `/share/{token}` pop-in link: the backend
 * `share_token` is generated on demand the first time the owner triggers any
 * action (privacy: collections never shared by link never have a token in the
 * database). PUBLIC collections are readable without an account, so we skip the
 * token entirely and share the collection URL directly — no email gate; a
 * visitor who wants to *act* is asked to log in only at that point (login-to-act).
 * The resolved URL is cached locally for the rest of the session.
 *
 * The text that goes with the link names the collection's kind when it has one
 * (`kinds.<K>.withArticle`: "a stall", "a library of things", "a shed").
 *
 * The "QR code" action opens an HDS Dialog rendering a QR of that same link via
 * `qrcode.react` (client-side, no network). It is handy for sharing in person —
 * a guest scans it with their phone camera.
 */
export default function ShareCollectionMenu({
  collectionCode,
  collectionKind,
  collectionHeadline,
  isPublic,
  canTakeBack = false,
}) {
  const { t } = useTranslation();
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const { ensureShareUrl, copy, setUrl, toast, setToast } = useShareLink({
    code: collectionCode,
    kind: collectionKind,
    isPublic,
  });
  const [qrUrl, setQrUrl] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);
  const panelId = `share-menu-panel-${useId()}`;
  useDismissable({ open, setOpen, wrapperRef, buttonRef });

  // With the kind ("…, a library of things on OIUEEI…") when the collection has one;
  // the words it always had when it does not.
  const kind = collectionKind ? t(`kinds.${collectionKind}.withArticle`) : null;

  const buildEmailBody = (url) =>
    kind
      ? t('shareMenu.emailBodyKind', { headline: collectionHeadline, kind, url })
      : t('shareMenu.emailBody', { headline: collectionHeadline, url });

  const handleEmail = async (url) => {
    const subject = encodeURIComponent(
      t('shareMenu.emailSubject', { headline: collectionHeadline })
    );
    const body = encodeURIComponent(buildEmailBody(url));
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const handleWhatsApp = async (url) => {
    const text = encodeURIComponent(
      kind
        ? t('shareMenu.whatsappTextKind', { headline: collectionHeadline, kind, url })
        : t('shareMenu.whatsappText', { headline: collectionHeadline, url })
    );
    window.open(`https://wa.me/?text=${text}`, '_blank', 'noopener,noreferrer');
  };

  const trigger = async (action) => {
    if (action === 'copy') return copy();
    try {
      const url = await ensureShareUrl();
      if (action === 'email') return handleEmail(url);
      if (action === 'whatsapp') return handleWhatsApp(url);
      if (action === 'qr') return setQrUrl(url);
    } catch {
      setToast({ type: 'error', message: t('shareMenu.linkError') });
    }
  };

  // Revoke / rotate only apply to PRIVATE collections (a PUBLIC collection has no
  // share token to pull back — it's shared by its plain URL). Both let the owner
  // take back a bearer credential they've handed out (DESIGN §9 user data control).
  const doRotate = async () => {
    try {
      const res = await apiFetch(`/api/v1/collections/${collectionCode}/share-link/`, {
        method: 'POST',
        body: JSON.stringify({ rotate: true }),
      });
      if (!res.ok) throw new Error('rotate failed');
      const data = await res.json();
      setUrl(data.share_url);
      setToast({ type: 'success', message: t('shareMenu.rotated') });
    } catch {
      setToast({ type: 'error', message: t('shareMenu.linkError') });
    } finally {
      setConfirmAction(null);
    }
  };

  const doRevoke = async () => {
    try {
      const res = await apiFetch(`/api/v1/collections/${collectionCode}/share-link/`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('revoke failed');
      setUrl(null);
      setToast({ type: 'success', message: t('shareMenu.revoked') });
    } catch {
      setToast({ type: 'error', message: t('shareMenu.linkError') });
    } finally {
      setConfirmAction(null);
    }
  };

  // Picking an entry closes the panel and puts the focus back on the trigger (the
  // pressed button goes with the panel; a dialog that opens next returns the focus
  // to the trigger when it closes).
  const pick = (value) => {
    setOpen(false);
    buttonRef.current?.focus();
    if (value === 'rotate' || value === 'revoke') setConfirmAction(value);
    else trigger(value);
  };

  const entries = [
    { value: 'email', label: t('shareMenu.email'), icon: <IconEnvelope aria-hidden="true" /> },
    { value: 'copy', label: t('shareMenu.copy'), icon: <IconCopy aria-hidden="true" /> },
    {
      value: 'whatsapp',
      label: t('shareMenu.whatsapp'),
      icon: <IconWhatsapp aria-hidden="true" />,
    },
    { value: 'qr', label: t('shareMenu.qr'), icon: <IconCamera aria-hidden="true" /> },
  ];
  // Taking a link back only exists for a PRIVATE collection (see above), and in a
  // network only for its founder (`canTakeBack`): the server refuses anyone else.
  const credentialEntries =
    isPublic || !canTakeBack
      ? []
      : [
          {
            value: 'rotate',
            label: t('shareMenu.rotate'),
            icon: <IconArrowRedo aria-hidden="true" />,
          },
          {
            value: 'revoke',
            label: t('shareMenu.revoke'),
            icon: <IconCrossCircle aria-hidden="true" />,
          },
        ];
  const entryButton = (entry) => (
    <button key={entry.value} type="button" onClick={() => pick(entry.value)}>
      {entry.icon}
      <span>{entry.label}</span>
    </button>
  );

  const qrTitle = t('shareMenu.qrTitle', { headline: collectionHeadline });
  const titleId = `share-qr-title-${collectionCode}`;
  const confirmTitleId = `share-confirm-title-${collectionCode}`;

  return (
    <>
      {/* One discreet icon in the hero's top-right, in the corner row. Focus leaving
          the whole menu closes the panel; a `null` `relatedTarget` is not "left"
          (Safari does not focus a clicked button), as in `AccountMenu`. */}
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
      <span
        className="share-menu"
        ref={wrapperRef}
        onBlur={(e) => {
          if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setOpen(false);
        }}
      >
        <button
          type="button"
          ref={buttonRef}
          className="share-menu-trigger"
          aria-label={t('shareMenu.label')}
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={() => setOpen((v) => !v)}
        >
          <IconShare aria-hidden="true" />
        </button>
        {open && (
          <div id={panelId} className="share-menu-panel">
            {entries.map(entryButton)}
            {credentialEntries.length > 0 && (
              <>
                <hr className="share-menu-divider" />
                {credentialEntries.map(entryButton)}
              </>
            )}
          </div>
        )}
      </span>
      {qrUrl && (
        <ThemedDialog
          id={`share-qr-${collectionCode}`}
          aria-labelledby={titleId}
          isOpen
          close={() => setQrUrl(null)}
          closeButtonLabelText={t('shareMenu.qrClose')}
        >
          <ThemedDialog.Header id={titleId} title={qrTitle} />
          <ThemedDialog.Content>
            <p>{t('shareMenu.qrHelper')}</p>
            <div className="share-qr-code">
              <Suspense
                fallback={
                  <div
                    style={{
                      width: 232,
                      height: 232,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                    role="status"
                    aria-live="polite"
                  >
                    <LoadingSpinner small loadingText={t('common.loading')} />
                  </div>
                }
              >
                <QRCodeSVG value={qrUrl} size={232} level="M" marginSize={2} title={qrTitle} />
              </Suspense>
            </div>
            <p className="share-qr-url">{qrUrl}</p>
          </ThemedDialog.Content>
          <ThemedDialog.ActionButtons>
            <Button onClick={() => setQrUrl(null)} style={btnStyle}>
              {t('shareMenu.qrClose')}
            </Button>
            <Button
              variant="secondary"
              iconStart={<IconCopy aria-hidden="true" />}
              onClick={() => copy(qrUrl)}
              style={btnSecondaryStyle}
            >
              {t('shareMenu.copy')}
            </Button>
          </ThemedDialog.ActionButtons>
        </ThemedDialog>
      )}
      {confirmAction && (
        <ThemedDialog
          id={`share-confirm-${collectionCode}`}
          aria-labelledby={confirmTitleId}
          isOpen
          close={() => setConfirmAction(null)}
          closeButtonLabelText={t('shareMenu.confirmCancel')}
        >
          <ThemedDialog.Header id={confirmTitleId} title={t(`shareMenu.${confirmAction}Title`)} />
          <ThemedDialog.Content>
            <p>{t(`shareMenu.${confirmAction}Body`)}</p>
          </ThemedDialog.Content>
          <ThemedDialog.ActionButtons>
            <Button onClick={confirmAction === 'rotate' ? doRotate : doRevoke} style={btnStyle}>
              {t(`shareMenu.${confirmAction}Confirm`)}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setConfirmAction(null)}
              style={btnSecondaryStyle}
            >
              {t('shareMenu.confirmCancel')}
            </Button>
          </ThemedDialog.ActionButtons>
        </ThemedDialog>
      )}
      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </>
  );
}
