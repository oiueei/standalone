import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Linkbox, Notification, Tag, TextArea, TextInput } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingLinkbox from '../components/ThingLinkbox';

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [showWelcome, setShowWelcome] = useState(!!location.state?.fromInvite && !localStorage.getItem('seenWelcome'));
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [broadcastSubject, setBroadcastSubject] = useState('');
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState(null);
  useEffect(() => { document.title = collection ? t('titles.collection', { headline: collection.headline }) : t('titles.collectionDefault'); }, [collection, t]);

  useEffect(() => {
    if (location.state?.fromInvite) {
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
    const userCode = localStorage.getItem('userCode');
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchCollection = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setCollection(data);
        } else if (res.status === 403) {
          setError(t('collectionPage.noPermission'));
        } else if (res.status === 404) {
          setError(t('collectionPage.notFound'));
        } else {
          setError(t('collectionPage.errorLoading'));
        }
      } catch {
        setError(t('common.connectionError'));
      }
    };
    fetchCollection();
  }, [code, navigate, t]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label={t('common.error')} type="error">{error}</Notification>
      </div>
    );
  }

  if (!collection) {
    return <LoadingSpinner />;
  }

  const handleBroadcast = async () => {
    setBroadcastSending(true);
    setBroadcastResult(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/broadcast/`, {
        method: 'POST',
        body: JSON.stringify({ subject: broadcastSubject, message: broadcastMessage }),
      });
      const data = await res.json();
      if (res.ok) {
        setBroadcastResult({ type: 'success', message: t('broadcast.sent', { count: data.recipients }) });
        setBroadcastSubject('');
        setBroadcastMessage('');
      } else {
        setBroadcastResult({ type: 'error', message: data.error || t('common.error') });
      }
    } catch {
      setBroadcastResult({ type: 'error', message: t('common.connectionError') });
    }
    setBroadcastSending(false);
  };

  const isOwner = localStorage.getItem('userCode') === collection.owner;
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': tc.color_02 ? `var(--color-${tc.color_02})` : undefined,
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          {!showWelcome && (
            <BackLink to="/" label={t('common.home')} />
          )}
          <h1 className="form-hero-title">
            {collection.headline}
            {collection.mode === 'COMMUNITY' && (
              <>{' '}<Tag theme={{ '--tag-background': 'var(--color-engel)', '--tag-color': 'var(--color-black-90)' }}>{t('collectionPage.communityTag')}</Tag></>
            )}
            {collection.is_swap && (
              <>{' '}<Tag theme={{ '--tag-background': 'var(--color-coat-of-arms-light)', '--tag-color': 'var(--color-white)' }}>{t('swap.swapCollection')}</Tag></>
            )}
          </h1>
          {collection.description && <p className="form-hero-text">{collection.description}</p>}
          {!isOwner && collection.owner_name && (
            <p className="form-hero-text" style={{ opacity: 0.75, fontSize: 'var(--fontsize-body-m)' }}>
              <strong>{t('collectionPage.owner')}</strong> <Link to={`/${collection.owner}`} className="owner-link">{collection.owner_name}</Link>
            </p>
          )}
          {isOwner && (
            <>
            <div className="spacer-m"></div>
            <div className="button-row-wide">
              <Link to={`/collections/${code}/edit`}>
                <Button style={btnStyle}>{t('collectionPage.editCollection')}</Button>
              </Link>
              <Link to={`/collections/${code}/add`}>
                <Button variant="secondary" style={btnSecondaryStyle}>{t('collectionPage.addThing')}</Button>
              </Link>
              <Link to={`/collections/${code}/invites`}>
                <Button variant="secondary" style={btnSecondaryStyle}>{t('collectionPage.manageGuests')}</Button>
              </Link>
            </div>
            </>
          )}
          {!isOwner && collection.mode === 'COMMUNITY' && (
            <>
            <div className="spacer-m"></div>
            <div className="button-row-wide">
              <Link to={`/collections/${code}/add`}>
                <Button variant="secondary" style={btnSecondaryStyle}>{t('collectionPage.addThing')}</Button>
              </Link>
            </div>
            </>
          )}
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
      {isOwner && collection.status === 'INACTIVE' && (
        <Notification label={t('common.notice')} type="info" style={{ marginBottom: 'var(--spacing-m)' }}>
          {t('collectionPage.inactiveNotice')}
        </Notification>
      )}

      {showWelcome && (
        <div className="linkbox-full-width">
        <Linkbox
          href="/welcome"
          onClick={(e) => {
            e.preventDefault();
            setShowWelcome(false);
            navigate('/welcome', { state: { collectionHeadline: collection.headline } });
          }}
          heading={t('collectionPage.welcomeHeading')}
          text={t('collectionPage.welcomeText')}
          linkAriaLabel={t('collectionPage.welcomeAriaLabel')}
          linkboxAriaLabel={t('collectionPage.welcomeHeading')}
          border
        />
        <div className="spacer-l" />
        </div>
      )}

      <h2>{t('collectionPage.things')}</h2>
      <div className="spacer-m" />
      {collection.things.filter((t) => t.status !== 'INACTIVE').length === 0 ? (
        <p>{t('collectionPage.noThings')}{(isOwner || collection.mode === 'COMMUNITY') && <> <Link to={`/collections/${code}/add`}>{t('collectionPage.addOne')}</Link>.</>}</p>
      ) : (
        <div className="things-grid">
          {[...collection.things].filter((t) => t.status !== 'INACTIVE').sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
            <ThingLinkbox
              key={thing.code}
              thing={thing}
              userCode={localStorage.getItem('userCode')}
              collectionCode={code}
              collectionHeadline={collection.headline}
              collectionOwner={collection.owner}
              onDelete={(thingCode) => setCollection((prev) => ({
                ...prev,
                things: prev.things.filter((t) => t.code !== thingCode),
              }))}
              onRemoveFromCollection={(thingCode) => setCollection((prev) => ({
                ...prev,
                things: prev.things.filter((t) => t.code !== thingCode),
              }))}
              onUpdateThing={(thingCode, updates) => setCollection((prev) => ({
                ...prev,
                things: prev.things.map((t) =>
                  t.code === thingCode ? { ...t, ...updates } : t
                ),
              }))}
            />
          ))}
        </div>
      )}

      {isOwner && collection.invites.length > 0 && (
        <>
          <div className="spacer-l" />
          <h2>{t('broadcast.heading')}</h2>
          <div className="spacer-m" />
          {!broadcastOpen ? (
            <Button variant="secondary" style={btnSecondaryStyle} onClick={() => setBroadcastOpen(true)}>
              {t('broadcast.openButton')}
            </Button>
          ) : (
            <div className="form-grid">
              <TextInput
                id="broadcast-subject"
                label={t('broadcast.subjectLabel')}
                value={broadcastSubject}
                onChange={(e) => setBroadcastSubject(e.target.value)}
                maxLength={64}
                required
              />
              <TextArea
                id="broadcast-message"
                label={t('broadcast.messageLabel')}
                value={broadcastMessage}
                onChange={(e) => setBroadcastMessage(e.target.value)}
                maxLength={256}
                required
              />
              {broadcastResult && (
                <Notification
                  label={broadcastResult.type === 'success' ? t('common.sent') : t('common.error')}
                  type={broadcastResult.type}
                  style={{ marginBottom: 'var(--spacing-s)' }}
                  dismissible
                  onClose={() => setBroadcastResult(null)}
                >
                  {broadcastResult.message}
                </Notification>
              )}
              <div className="button-row-wide">
                <Button
                  style={btnStyle}
                  onClick={handleBroadcast}
                  disabled={broadcastSending || !broadcastSubject.trim() || !broadcastMessage.trim()}
                >
                  {broadcastSending ? t('broadcast.sending') : t('broadcast.sendButton')}
                </Button>
                <Button variant="secondary" style={btnSecondaryStyle} onClick={() => { setBroadcastOpen(false); setBroadcastResult(null); }}>
                  {t('common.close')}
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {isOwner && collection.things.some((t) => t.status === 'INACTIVE') && (
        <>
          <div className="spacer-l" />
          <h2>{t('collectionPage.inactiveThings')}</h2>
          <div className="spacer-m" />
          <div className="things-grid">
            {[...collection.things].filter((t) => t.status === 'INACTIVE').sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
              <ThingLinkbox
                key={thing.code}
                thing={thing}
                userCode={localStorage.getItem('userCode')}
                collectionCode={code}
                collectionHeadline={collection.headline}
                collectionOwner={collection.owner}
                onDelete={(thingCode) => setCollection((prev) => ({
                  ...prev,
                  things: prev.things.filter((t) => t.code !== thingCode),
                }))}
                onRemoveFromCollection={(thingCode) => setCollection((prev) => ({
                  ...prev,
                  things: prev.things.filter((t) => t.code !== thingCode),
                }))}
                onUpdateThing={(thingCode, updates) => setCollection((prev) => ({
                  ...prev,
                  things: prev.things.map((t) =>
                    t.code === thingCode ? { ...t, ...updates } : t
                  ),
                }))}
              />
            ))}
          </div>
        </>
      )}

      </div>
    </div>
  );
}
