import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { IconEnvelope, IconShare, IconWhatsapp, Select } from 'hds-react';
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
 * owner triggers any of the three actions (privacy: collections that are
 * never shared by link never have a token in the database). The URL is
 * cached locally for the rest of the session to avoid extra round trips.
 */
export default function ShareCollectionMenu({ collectionCode, collectionHeadline, ownerName }) {
  const { t, i18n } = useTranslation();
  const [toast, setToast] = useState(null);
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
  ];

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
        visibleOptions={3}
      />
      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </>
  );
}
