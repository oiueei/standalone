import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Koros, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingLinkbox from '../components/ThingLinkbox';

export default function HomePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [myThings, setMyThings] = useState(null);
  const [invitedThings, setInvitedThings] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const userCode = localStorage.getItem('userCode');
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchMe = async () => {
      try {
        const res = await apiFetch('/api/v1/auth/me/');
        if (res.ok) {
          const data = await res.json();
          if (data.code) localStorage.setItem('userCode', data.code);
          if (data.theeeme_colors) localStorage.setItem('theeemeColors', JSON.stringify(data.theeeme_colors));
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
    return <LoadingSpinner />;
  }

  const allThings = [
    ...(myThings || []),
    ...(invitedThings || []),
  ].sort((a, b) => new Date(b.created) - new Date(a.created));

  const tc = user.theeeme_colors || {};
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
          <h1 className="form-hero-title" style={{ paddingTop: 'var(--spacing-xl)' }}>Hello, {user.name || user.email}</h1>
          {user.headline && <p className="form-hero-text">{user.headline}</p>}
          <div className="button-row-wide">
            <Link to="/collections/new">
              <Button style={btnStyle}>Create collection</Button>
            </Link>
            <Link to="/me/edit">
              <Button variant="secondary" style={btnSecondaryStyle}>Edit profile</Button>
            </Link>
            <Link to="/my-bookings">
              <Button variant="secondary" style={btnSecondaryStyle}>My requests</Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type="basic"
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">

      <h2>My collections</h2>
      {myCollections === null ? (
        <p className="text-muted">Loading collections...</p>
      ) : myCollections.length === 0 ? (
        <p>You have no collections yet. <Link to="/collections/new">Create your first collection</Link> to get started.</p>
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
        <p className="text-muted">Loading collections...</p>
      ) : invitedCollections.length === 0 ? (
        <p>No one has shared a collection with you yet.</p>
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
        <p className="text-muted">Loading things...</p>
      ) : allThings.length === 0 ? (
        <p>No things yet. Add things to your collections to see them here.</p>
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
    </div>
  );
}
