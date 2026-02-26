import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import ThingLinkbox from '../components/ThingLinkbox';
import placeholderImg from '../assets/image-m.png';

export default function HomePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [myThings, setMyThings] = useState(null);
  const [invitedThings, setInvitedThings] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchMe = async () => {
      try {
        const res = await apiFetch('/api/v1/auth/me/');
        if (res.ok) {
          const data = await res.json();
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        }
      } catch {
        setError('Connection error.');
      }
    };

    const fetchMyCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/collections/');
        if (res.ok) {
          const data = await res.json();
          setMyCollections(data.results);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/invited-collections/');
        if (res.ok) {
          const data = await res.json();
          setInvitedCollections(data);
        }
      } catch { /* silently fail */ }
    };

    const fetchMyThings = async () => {
      try {
        const res = await apiFetch('/api/v1/things/');
        if (res.ok) {
          const data = await res.json();
          setMyThings(data.results);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedThings = async () => {
      try {
        const res = await apiFetch('/api/v1/invited-things/');
        if (res.ok) {
          const data = await res.json();
          setInvitedThings(data.results);
        }
      } catch { /* silently fail */ }
    };

    fetchMe();
    fetchMyCollections();
    fetchInvitedCollections();
    fetchMyThings();
    fetchInvitedThings();
  }, [navigate]);

  const updateThing = (thingCode, updates) => {
    setMyThings((prev) => prev && prev.map((t) => t.code === thingCode ? { ...t, ...updates } : t));
    setInvitedThings((prev) => prev && prev.map((t) => t.code === thingCode ? { ...t, ...updates } : t));
  };

  const deleteThing = (thingCode) => {
    setMyThings((prev) => prev && prev.filter((t) => t.code !== thingCode));
    setInvitedThings((prev) => prev && prev.filter((t) => t.code !== thingCode));
  };

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!user) {
    return <div className="page-container"><p>Loading...</p></div>;
  }

  const allThings = [
    ...(myThings || []),
    ...(invitedThings || []),
  ].sort((a, b) => new Date(b.created) - new Date(a.created));

  return (
    <div className="page-container">
      <img
        src={user.hero_url || placeholderImg}
        alt={user.name || user.email}
        style={{ width: '100%', maxHeight: '300px', objectFit: 'cover', borderRadius: '8px', marginBottom: '1rem' }}
      />
      <h1 className="page-title">Hello, {user.name || user.email}</h1>
      {user.headline && <p>{user.headline}</p>}

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <Link to="/collections/new">
          <Button>Create collection</Button>
        </Link>
        <Link to="/me/edit">
          <Button>Edit profile</Button>
        </Link>
      </div>

      <h2>My collections</h2>
      {myCollections === null ? (
        <p>Loading...</p>
      ) : myCollections.length === 0 ? (
        <p>You have no collections.</p>
      ) : (
        <ul>
          {myCollections.map((c) => (
            <li key={c.code}>
              <Link to={`/collections/${c.code}`}>
                <strong>{c.headline}</strong>
              </Link>
              {' — '}
              {c.status} · {c.things.length} things · {c.invites.length} guests
            </li>
          ))}
        </ul>
      )}

      <h2>Shared with me</h2>
      {invitedCollections === null ? (
        <p>Loading...</p>
      ) : invitedCollections.length === 0 ? (
        <p>You have no collection invitations.</p>
      ) : (
        <ul>
          {invitedCollections.map((c) => (
            <li key={c.code}>
              <Link to={`/collections/${c.code}`}>
                <strong>{c.headline}</strong>
              </Link>
              {' — '}
              {c.status} · {c.things.length} things · {c.invites.length} guests
            </li>
          ))}
        </ul>
      )}

      <h2>All things</h2>
      {myThings === null || invitedThings === null ? (
        <p>Loading...</p>
      ) : allThings.length === 0 ? (
        <p>You have no things.</p>
      ) : (
        <div className="things-grid">
          {allThings.map((thing) => (
            <ThingLinkbox
              key={thing.code}
              thing={thing}
              userCode={localStorage.getItem('userCode')}
              onDelete={deleteThing}
              onUpdateThing={updateThing}
            />
          ))}
        </div>
      )}
    </div>
  );
}
