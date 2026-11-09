import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router';
import { useTranslation, Trans } from 'react-i18next';
import { Button, IconSignout } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import ThingsGoNotice from '../components/ThingsGoNotice';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import LoadingSpinner from '../components/LoadingSpinner';
import { useCollectionBase } from '../hooks/useCollectionBase';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function LeaveCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = `${base}`;
  const headline = location.state?.headline || t('leaveCollection.thisCollection');

  useDocumentTitle(t('titles.leaveCollection'));

  const [leaving, setLeaving] = useState(false);
  const [toast, setToast] = useState(null);
  // The member's own things in this group, which leave with them. Leaving does not
  // depend on this: if the group cannot be read the page works without the notice.
  const [goingTitles, setGoingTitles] = useState([]);
  // The same read gives the group's colours; the confirmation is not painted before it
  // has answered (the app's palette would show for an instant). A group that cannot be
  // read settles with no palette and the page keeps the app's.
  const [palette, setPalette] = useState(null);
  const [settled, setSettled] = useState(false);
  useCollectionTheeeme(palette?.colors, palette?.koro);
  // The group's own language, as the other pages of a collection speak it. The load below
  // keeps `t` out of its dependencies: this hook changes the language as the answer lands.
  const [groupLanguage, setGroupLanguage] = useState('');
  const [groupTexts, setGroupTexts] = useState([]);
  useCollectionLanguage(groupLanguage, groupTexts);

  useEffect(() => {
    const userCode = localStorage.getItem('userCode');
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (cancelled) return;
        setPalette({ colors: data.theeeme_colors, koro: data.koro });
        setGroupLanguage(data.language || '');
        setGroupTexts([data.headline]);
        setGoingTitles(
          (data.things || [])
            .filter((thing) => thing.owner === userCode)
            .map((thing) => thing.headline)
        );
      } catch {
        // No notice; the exit still works.
      } finally {
        if (!cancelled) setSettled(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  const handleLeave = async () => {
    setLeaving(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/leave/`, { method: 'POST' });
      if (res.ok) {
        navigate('/');
      } else {
        setToast({ type: 'error', message: t('leaveCollection.errorLeaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setLeaving(false);
    }
  };

  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  if (!settled) return <LoadingSpinner />;

  return (
    <PageLayout
      title={t('leaveCollection.pageTitle', { headline })}
      backTo={backPath}
      backLabel={headline}
    >
      <p>
        <Trans
          i18nKey="leaveCollection.warning"
          values={{ headline }}
          components={[<strong key="0" />]}
        />
      </p>
      <ThingsGoNotice
        titles={goingTitles}
        label={t('leaveCollection.thingsLabel')}
        body={(count, list) => t('leaveCollection.thingsBody', { count, list })}
      />
      <div className="spacer-xs" />
      <div className="form-grid">
        <Button
          fullWidth
          disabled={leaving}
          onClick={handleLeave}
          style={btnStyle}
          iconStart={<IconSignout aria-hidden="true" />}
        >
          {leaving ? t('leaveCollection.leaving') : t('leaveCollection.leave')}
        </Button>
        <Button
          variant="secondary"
          fullWidth
          onClick={() => navigate(backPath)}
          style={btnSecondaryStyle}
        >
          {t('common.cancel')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
