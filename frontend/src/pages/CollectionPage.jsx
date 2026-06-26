import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Linkbox, Notification, Tag, TextArea } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownText from '../components/MarkdownText';
import ShareCollectionMenu from '../components/ShareCollectionMenu';
import ThingLinkbox from '../components/ThingLinkbox';
import useTheeeme from '../hooks/useTheeeme';

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { tc, koro, btnStyle, btnSecondaryStyle } = useTheeeme();
  const [showWelcome, setShowWelcome] = useState(!!location.state?.fromInvite && !localStorage.getItem('seenWelcome'));
  const [collection, setCollection] = useState(null);
  const [statsError, setStatsError] = useState(false);
  const [error, setError] = useState('');
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState(null);
  const [activeTag, setActiveTag] = useState(null);
  useEffect(() => { document.title = collection ? t('titles.collection', { headline: collection.headline }) : t('titles.collectionDefault'); }, [collection, t]);

  useEffect(() => {
    if (location.state?.fromInvite) {
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
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
        body: JSON.stringify({ message: broadcastMessage }),
      });
      const data = await res.json();
      if (res.ok) {
        setBroadcastResult({ type: 'success', message: t('broadcast.sent', { count: data.recipients }) });
        setBroadcastMessage('');
      } else {
        setBroadcastResult({ type: 'error', message: data.error || t('common.error') });
      }
    } catch {
      setBroadcastResult({ type: 'error', message: t('common.connectionError') });
    }
    setBroadcastSending(false);
  };

  const handleDownloadStats = async () => {
    setStatsError(false);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/stats/`);
      if (!res.ok) throw new Error('stats');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${code}-stats.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setStatsError(true);
    }
  };

  const isOwner = localStorage.getItem('userCode') === collection.owner;
  const isAuthenticated = !!localStorage.getItem('userCode');

  // Active (non-inactive) things, optionally narrowed to the selected tag chip.
  const visibleThings = collection.things.filter((thg) => thg.status !== 'INACTIVE');
  const collectionTags = collection.tags || [];
  const effectiveTag = activeTag && collectionTags.includes(activeTag) ? activeTag : null;
  const shownThings = effectiveTag
    ? visibleThings.filter((thg) => (thg.tags || []).includes(effectiveTag))
    : visibleThings;
  // A collection locked to one thing type makes the per-card "Type = X" row
  // redundant — hide it (swap/share force a single type; an allowlist of one).
  const singleType = collection.is_swap || collection.is_share
    || (collection.allowed_thing_types || []).length === 1;

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
            {collection.is_share && (
              <>{' '}<Tag theme={{ '--tag-background': 'var(--color-tram)', '--tag-color': 'var(--color-white)' }}>{t('share.shareCollection')}</Tag></>
            )}
            {collection.is_minimalist && (
              <>{' '}<Tag theme={{ '--tag-background': 'var(--color-summer)', '--tag-color': 'var(--color-black-90)' }}>{t('minimalist.albumTag')}</Tag></>
            )}
            {isOwner && (
              <>{' '}<Tag theme={collection.visibility === 'PUBLIC'
                ? { '--tag-background': 'var(--color-success)', '--tag-color': 'var(--color-white)' }
                : { '--tag-background': 'var(--color-black-20)', '--tag-color': 'var(--color-black-90)' }}>
                {collection.visibility === 'PUBLIC' ? t('visibility.publicTag') : t('visibility.privateTag')}
              </Tag></>
            )}
          </h1>
          {collection.description && <MarkdownText text={collection.description} className="form-hero-text" />}
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
              <Button variant="secondary" style={btnSecondaryStyle} onClick={handleDownloadStats}>
                {t('stats.downloadStats')}
              </Button>
            </div>
            {statsError && (
              <Notification type="error" size="small" style={{ marginTop: 'var(--spacing-xs)' }}>
                {t('stats.downloadStatsError')}
              </Notification>
            )}
            <div className="spacer-s"></div>
            <div className="spacer-l" />
            <div className="share-menu-wrap">
              <ShareCollectionMenu
                collectionCode={code}
                collectionHeadline={collection.headline}
                ownerName={collection.owner_name}
              />
            </div>
            </>
          )}
          {isAuthenticated && !isOwner && collection.mode === 'COMMUNITY' && (
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
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
      {isOwner && collection.status === 'INACTIVE' && (
        <Notification label={t('common.notice')} type="info" style={{ marginBottom: 'var(--spacing-m)' }}>
          {t('collectionPage.inactiveNotice')}
        </Notification>
      )}
      {collection.is_paused && (
        <Notification label={t('pause.bannerLabel')} type="alert" style={{ marginBottom: 'var(--spacing-m)' }}>
          {collection.pause_message}
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
      {visibleThings.length > 0 && collectionTags.length > 0 && (
        <div className="tag-filter-bar">
          <button
            type="button"
            className="tag-chip"
            aria-pressed={!effectiveTag}
            onClick={() => setActiveTag(null)}
          >
            {t('collectionPage.allTags')} ({visibleThings.length})
          </button>
          {collectionTags.map((tag) => {
            const count = visibleThings.filter((thg) => (thg.tags || []).includes(tag)).length;
            return (
              <button
                key={tag}
                type="button"
                className="tag-chip"
                aria-pressed={effectiveTag === tag}
                onClick={() => setActiveTag(effectiveTag === tag ? null : tag)}
              >
                {tag} ({count})
              </button>
            );
          })}
        </div>
      )}
      {visibleThings.length === 0 ? (
        <>
          <p>{t('collectionPage.noThings')}{(isOwner || collection.mode === 'COMMUNITY') && <> <Link to={`/collections/${code}/add`}>{t('collectionPage.addOne')}</Link>.</>}</p>
          <div className="spacer-xxs" />
          {(isOwner || collection.mode === 'COMMUNITY') && !collection.is_minimalist && (
            <p><Link to={`/collections/${code}/add#bulk-add`}>{t('collectionPage.addManyCsv')}</Link></p>
          )}
        </>
      ) : shownThings.length === 0 ? (
        <p>{t('collectionPage.noThingsForTag')}</p>
      ) : (
        <div className="things-grid">
          {[...shownThings].sort((a, b) => {
            return new Date(b.created) - new Date(a.created);
          }).map((thing) => (
            <ThingLinkbox
              key={thing.code}
              thing={thing}
              userCode={localStorage.getItem('userCode')}
              collectionCode={code}
              collectionHeadline={collection.headline}
              collectionOwner={collection.owner}
              collectionMode={collection.mode}
              minimalist={collection.is_minimalist}
              isPaused={collection.is_paused}
              hideType={singleType}
              canAct={isAuthenticated}
              loginToAct={!isAuthenticated}
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
                  disabled={broadcastSending || !broadcastMessage.trim()}
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
            {[...collection.things].filter((t) => t.status === 'INACTIVE').sort((a, b) => {
              return new Date(b.created) - new Date(a.created);
            }).map((thing) => (
              <ThingLinkbox
                key={thing.code}
                thing={thing}
                userCode={localStorage.getItem('userCode')}
                collectionCode={code}
                collectionHeadline={collection.headline}
                collectionOwner={collection.owner}
                collectionMode={collection.mode}
                minimalist={collection.is_minimalist}
                hideType={singleType}
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
