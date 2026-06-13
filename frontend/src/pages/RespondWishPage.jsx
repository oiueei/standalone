import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Notification, NumberInput, TextArea, TextInput } from 'hds-react';
import { WISH_KIND_BY_SLUG } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

/**
 * Short answer form for a wish: "Sé dónde" (message + link) and
 * "Puedo hacértelo" (message + offer/price). The "Tengo esto" answer reuses
 * the publish-listing flow (AddThingPage) instead of this page.
 */
export default function RespondWishPage() {
  const { code, thingCode, kind: kindSlug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();

  const userCode = localStorage.getItem('userCode');
  const kind = WISH_KIND_BY_SLUG[kindSlug];

  const [message, setMessage] = useState('');
  const [url, setUrl] = useState('');
  const [fee, setFee] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [toast, setToast] = useState(null);

  const isKnowWhere = kind === 'KNOW_WHERE';
  const title = isKnowWhere ? t('wishes.knowWhereTitle') : t('wishes.canMakeTitle');

  useEffect(() => { document.title = title; }, [title]);
  useEffect(() => {
    if (!userCode) navigate('/login');
    else if (!kind) navigate('/');
  }, [userCode, kind, navigate]);

  const backPath = location.state?.backPath
    || (code ? `/collections/${code}/things/${thingCode}` : `/things/${thingCode}`);
  const backLabel = location.state?.backLabel || t('common.back');

  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || {}; } catch { return {}; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  const handleSubmit = async () => {
    if (!message.trim()) {
      setErrors({ message: t('wishes.messageRequired') });
      return;
    }
    setErrors({});
    setSubmitting(true);
    setToast(null);
    const body = { kind, message: message.trim() };
    if (isKnowWhere && url.trim()) body.url = url.trim();
    if (!isKnowWhere && fee !== '') body.fee = fee;
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/responses/`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSent(true);
      } else {
        setToast({ type: 'error', message: t('wishes.errorResponding') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{title}</h1>

        {sent ? (
          <Notification type="success" label={t('wishes.responseSent')}>
            <Button style={{ ...btnStyle, marginTop: 'var(--spacing-s)' }} onClick={() => navigate(backPath)}>
              {t('common.back')}
            </Button>
          </Notification>
        ) : (
          <>
            <div className="form-grid">
              <TextArea
                id="respond-message"
                label={t('wishes.messageLabel')}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
                invalid={!!errors.message}
                errorText={errors.message}
                helperText={`${message.length}/256`}
              />
              {isKnowWhere ? (
                <TextInput
                  id="respond-url"
                  label={t('wishes.urlLabel')}
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              ) : (
                <NumberInput
                  id="respond-fee"
                  label={t('wishes.feeLabel')}
                  value={fee === '' ? '' : Number(fee)}
                  onChange={(e) => setFee(e.target.value)}
                  min={0}
                  unit="EUR"
                />
              )}
            </div>
            <div className="form-actions">
              <Button style={{ ...btnStyle, width: '100%' }} disabled={submitting} onClick={handleSubmit}>
                {submitting ? t('common.sending') : t('wishes.submit')}
              </Button>
            </div>
          </>
        )}

        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
