import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { Button, Koros, Linkbox, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingLinkbox from '../components/ThingLinkbox';

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [showWelcome, setShowWelcome] = useState(!!location.state?.fromInvite && !localStorage.getItem('seenWelcome'));
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { document.title = collection ? `${collection.headline} — OIUEEI` : 'Collection — OIUEEI'; }, [collection]);

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
          setError('You do not have permission to view this collection.');
        } else if (res.status === 404) {
          setError('Collection not found.');
        } else {
          setError('Error loading collection.');
        }
      } catch {
        setError('Connection error.');
      }
    };
    fetchCollection();
  }, [code, navigate]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!collection) {
    return <LoadingSpinner />;
  }

  const isOwner = localStorage.getItem('userCode') === collection.owner;
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          {!showWelcome && (
            <BackLink to="/" label="Home" />
          )}
          <h1 className="form-hero-title">{collection.headline}</h1>
          {collection.description && <p className="form-hero-text">{collection.description}</p>}
          {!isOwner && collection.owner_name && (
            <p className="form-hero-text" style={{ opacity: 0.75, fontSize: 'var(--fontsize-body-m)' }}>
              <strong>Owner.</strong> <Link to={`/${collection.owner}`} className="owner-link">{collection.owner_name}</Link>
            </p>
          )}
          {isOwner && (
            <>
            <div className="spacer-m"></div>
            <div className="button-row-wide">
              <Link to={`/collections/${code}/edit`}>
                <Button style={btnStyle}>Edit collection</Button>
              </Link>
              <Link to={`/collections/${code}/add`}>
                <Button variant="secondary" style={btnSecondaryStyle}>Add thing</Button>
              </Link>
              <Link to={`/collections/${code}/invites`}>
                <Button variant="secondary" style={btnSecondaryStyle}>Manage guests</Button>
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
        <Notification label="Notice" type="info" style={{ marginBottom: 'var(--spacing-m)' }}>
          This collection is inactive. It is not visible to guests.
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
          heading="Welcome to OIUEEI!"
          text="Want to know more? Click here!"
          linkAriaLabel="Go to Welcome"
          linkboxAriaLabel="Welcome to OIUEEI!"
          border
        />
        <div className="spacer-l" />
        </div>
      )}

      <h2>Things</h2>
      <div className="spacer-m" />
      {collection.things.filter((t) => t.status !== 'INACTIVE').length === 0 ? (
        <p>No things in this collection yet.{isOwner && <> <Link to={`/collections/${code}/add`}>Add one</Link>.</>}</p>
      ) : (
        <div className="things-grid">
          {[...collection.things].filter((t) => t.status !== 'INACTIVE').sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
            <ThingLinkbox
              key={thing.code}
              thing={thing}
              userCode={localStorage.getItem('userCode')}
              collectionCode={code}
              collectionHeadline={collection.headline}
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

      {isOwner && collection.things.some((t) => t.status === 'INACTIVE') && (
        <>
          <div className="spacer-l" />
          <h2>Inactive things</h2>
          <div className="spacer-m" />
          <div className="things-grid">
            {[...collection.things].filter((t) => t.status === 'INACTIVE').sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
              <ThingLinkbox
                key={thing.code}
                thing={thing}
                userCode={localStorage.getItem('userCode')}
                collectionCode={code}
                collectionHeadline={collection.headline}
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
