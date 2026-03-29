import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Koros, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingLinkbox from '../components/ThingLinkbox';

export default function HomePage() {
  const navigate = useNavigate();
  useEffect(() => { document.title = 'Home — OIUEEI'; }, []);
  const [user, setUser] = useState(null);
  const [myThings, setMyThings] = useState(null);
  const [invitedThings, setInvitedThings] = useState(null);
  const [pendingInvitations, setPendingInvitations] = useState([]);
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
          if (data.koro) localStorage.setItem('koro', data.koro);
          localStorage.setItem('seenWelcome', 'true');
          setUser(data);
        }
      } catch {
        setError('Connection error.');
      }
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

    const fetchPendingInvitations = async () => {
      try {
        const res = await apiFetch('/api/v1/my-invitations/');
        if (res.ok) {
          const data = await res.json();
          setPendingInvitations(data);
        }
      } catch { /* silently fail */ }
    };

    fetchMe();
    fetchMyThings();
    fetchInvitedThings();
    fetchPendingInvitations();
  }, [navigate]);

  const updateThing = (thingCode, updates) => {
    setMyThings((prev) => prev && prev.map((t) => t.code === thingCode ? { ...t, ...updates } : t));
    setInvitedThings((prev) => prev && prev.map((t) => t.code === thingCode ? { ...t, ...updates } : t));
  };

  const deleteThing = (thingCode) => {
    setMyThings((prev) => prev && prev.filter((t) => t.code !== thingCode));
    setInvitedThings((prev) => prev && prev.filter((t) => t.code !== thingCode));
  };

  const dismissInvitation = (acceptCode) => {
    setPendingInvitations((prev) => prev.filter((inv) => inv.accept_code !== acceptCode));
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

  const activeThings = [
    ...(myThings || []).filter((t) => t.status !== 'INACTIVE'),
    ...(invitedThings || []).filter((t) => t.status !== 'INACTIVE'),
  ].sort((a, b) => new Date(b.created) - new Date(a.created));

  const inactiveMyThings = [...(myThings || [])].filter((t) => t.status === 'INACTIVE').sort((a, b) => new Date(b.created) - new Date(a.created));

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
            <Link to="/me">
              <Button variant="secondary" style={btnSecondaryStyle}>My profile</Button>
            </Link>
            <Link to="/my-bookings">
              <Button variant="secondary" style={btnSecondaryStyle}>My requests</Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={user.koro || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">

      {pendingInvitations.length > 0 && (
        <>
          {pendingInvitations.map((inv) => (
            <Notification
              key={inv.accept_code}
              label={`${inv.owner_name} has invited you to view`}
              type="info"
              dismissible
              closeButtonLabelText="Dismiss"
              onClose={() => dismissInvitation(inv.accept_code)}
              style={{ marginBottom: 'var(--spacing-s)' }}
            >
              <strong>{inv.collection_headline}</strong>
              <div style={{ marginTop: 'var(--spacing-xs)', display: 'flex', gap: 'var(--spacing-s)', flexWrap: 'wrap' }}>
                <Link to={`/verify/${inv.accept_code}`}>Accept invitation</Link>
                <Link to={`/verify/${inv.reject_code}`}>Decline invitation</Link>
              </div>
            </Notification>
          ))}
          <div className="spacer-m" />
        </>
      )}

      <h2>All things</h2>
      <div className="spacer-m" />
      {myThings === null || invitedThings === null ? (
        <p className="text-muted">Loading things...</p>
      ) : activeThings.length === 0 ? (
        <p>No things yet. Add things to your collections to see them here.</p>
      ) : (
        <div className="things-grid">
          {activeThings.map((thing) => (
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

      {inactiveMyThings.length > 0 && (
        <>
          <div className="spacer-l" />
          <h2>Inactive things</h2>
          <div className="spacer-m" />
          <div className="things-grid">
            {inactiveMyThings.map((thing) => (
              <ThingLinkbox
                key={thing.code}
                thing={thing}
                userCode={localStorage.getItem('userCode')}
                onDelete={deleteThing}
                onUpdateThing={updateThing}
              />
            ))}
          </div>
        </>
      )}
      </div>
    </div>
  );
}
