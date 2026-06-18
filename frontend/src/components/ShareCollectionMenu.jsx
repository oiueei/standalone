import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Dialog, IconCamera, IconEnvelope, IconShare, IconWhatsapp, Select } from 'hds-react';
import { QRCodeSVG } from 'qrcode.react';
import useTheeeme from '../hooks/useTheeeme';
import { apiFetch } from '../services/api';
import Toast from './Toast';

/**
 * Share menu for the CollectionPage hero (owner only).
 *
 * HDS Select is a form input by design — value persists after selection.
 * Here we hijack `onChange`/`onClose` to fire the action and reset the
 * value, so the Select behaves as a one-shot menu of share actions.
 *
 * The backend `share_token` is generated on demand the first time the
 * owner triggers any of the actions (privacy: collections that are
 * never shared by link never have a token in the database). The URL is
 * cached locally for the rest of the session to avoid extra round trips.
 *
 * The "QR code" action opens an HDS Dialog rendering a QR of the same
 * public share link via `qrcode.react` (client-side, no network). It is
 * handy for sharing in person — a guest scans it with their phone camera.
 */
export default function ShareCollectionMenu({ collectionCode, collectionHeadline, ownerName }) {
  const { t, i18n } = useTranslation();
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const [toast, setToast] = useState(null);
  const [qrUrl, setQrUrl] = useState(null);
  const cachedUrlRef = useRef(null);

  const ensureShareUrl = async () => {
    if (cachedUrlRef.current) return cachedUrlRef.current;
    const res = await apiFetch(`/api/v1/collections/${collectionCode}/share-link/`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('share-link request failed');
    const data = await res.json();
    cachedUrlRef.current = data.share_url;
    return data.share_url;
  };

  const buildEmailBody = (url) =>
    t('shareMenu.emailBody', {
      headline: collectionHeadline,
      url,
      name: ownerName || '',
    });

  const handleEmail = async (url) => {
    const subject = encodeURIComponent(
      t('shareMenu.emailSubject', { headline: collectionHeadline })
    );
    const body = encodeURIComponent(buildEmailBody(url));
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const handleCopy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setToast({ type: 'success', message: t('shareMenu.copied') });
    } catch {
      setToast({ type: 'error', message: t('shareMenu.copyError') });
    }
  };

  const handleWhatsApp = async (url) => {
    const text = encodeURIComponent(
      t('shareMenu.whatsappText', { headline: collectionHeadline, url })
    );
    window.open(`https://wa.me/?text=${text}`, '_blank', 'noopener,noreferrer');
  };

  const trigger = async (action) => {
    try {
      const url = await ensureShareUrl();
      if (action === 'email') return handleEmail(url);
      if (action === 'copy') return handleCopy(url);
      if (action === 'whatsapp') return handleWhatsApp(url);
      if (action === 'qr') return setQrUrl(url);
    } catch {
      setToast({ type: 'error', message: t('shareMenu.linkError') });
    }
  };

  const options = [
    {
      value: 'email',
      label: t('shareMenu.email'),
      iconStart: <IconEnvelope aria-hidden="true" />,
    },
    {
      value: 'copy',
      label: t('shareMenu.copy'),
      iconStart: <IconShare aria-hidden="true" />,
    },
    {
      value: 'whatsapp',
      label: t('shareMenu.whatsapp'),
      iconStart: <IconWhatsapp aria-hidden="true" />,
    },
    {
      value: 'qr',
      label: t('shareMenu.qr'),
      iconStart: <IconCamera aria-hidden="true" />,
    },
  ];

  const qrTitle = t('shareMenu.qrTitle', { headline: collectionHeadline });
  const titleId = `share-qr-title-${collectionCode}`;

  return (
    <>
      <Select
        id={`share-menu-${collectionCode}`}
        texts={{
          label: t('shareMenu.label'),
          placeholder: t('shareMenu.placeholder'),
          language: i18n.language?.startsWith('fi') ? 'fi' : 'en',
        }}
        options={options}
        value={[]}
        onChange={(selected) => {
          const picked = selected && selected.length > 0 ? selected[0] : null;
          if (picked && picked.value) {
            trigger(picked.value);
          }
        }}
        visibleOptions={4}
      />
      {qrUrl && (
        <Dialog
          id={`share-qr-${collectionCode}`}
          aria-labelledby={titleId}
          isOpen
          close={() => setQrUrl(null)}
          closeButtonLabelText={t('shareMenu.qrClose')}
        >
          <Dialog.Header id={titleId} title={qrTitle} />
          <Dialog.Content>
            <p>{t('shareMenu.qrHelper')}</p>
            <div className="share-qr-code">
              <QRCodeSVG value={qrUrl} size={232} level="M" marginSize={2} title={qrTitle} />
            </div>
            <p className="share-qr-url">{qrUrl}</p>
          </Dialog.Content>
          <Dialog.ActionButtons>
            <Button onClick={() => setQrUrl(null)} style={btnStyle}>
              {t('shareMenu.qrClose')}
            </Button>
            <Button
              variant="secondary"
              iconStart={<IconShare aria-hidden="true" />}
              onClick={() => handleCopy(qrUrl)}
              style={btnSecondaryStyle}
            >
              {t('shareMenu.copy')}
            </Button>
          </Dialog.ActionButtons>
        </Dialog>
      )}
      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </>
  );
}
