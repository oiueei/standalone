import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { Button, Linkbox, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import ThingLinkbox from '../components/ThingLinkbox';
import placeholderImg from '../assets/image-m.png';

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [showWelcome, setShowWelcome] = useState(!!location.state?.fromInvite);
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (location.state?.fromInvite) {
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
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
    return <div className="page-container"><p>Loading...</p></div>;
  }

  const isOwner = localStorage.getItem('userCode') === collection.owner;

  return (
    <div className="page-container">
      {!showWelcome && (
        <BackLink to="/" label="Home" />
      )}
      <img
        src={collection.hero_url || collection.thumbnail_url || placeholderImg}
        alt={collection.headline}
        style={{ width: '100%', maxHeight: '300px', objectFit: 'cover', borderRadius: '8px', marginBottom: '1rem' }}
      />
      <h1 className="page-title">{collection.headline}</h1>
      {collection.description && <p>{collection.description}</p>}
      {isOwner && (
        <p><strong>Status:</strong> {collection.status}</p>
      )}

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        {isOwner && (
          <Link to={`/collections/${code}/edit`}>
            <Button>Edit collection</Button>
          </Link>
        )}
        {isOwner && (
          <Link to={`/collections/${code}/add-thing`}>
            <Button>Add thing</Button>
          </Link>
        )}
        {isOwner && (
          <Link to={`/collections/${code}/invites`}>
            <Button>Manage guests</Button>
          </Link>
        )}
      </div>

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
        </div>
      )}

      <h2>Things</h2>
      {collection.things.length === 0 ? (
        <p>No things in this collection.</p>
      ) : (
        <div className="things-grid">
          {[...collection.things].sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
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

    </div>
  );
}
