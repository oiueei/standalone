import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Koros, Linkbox, Notification } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [error, setError] = useState('');

  const userCode = paramCode || localStorage.getItem('userCode');
  const isOwnProfile = !paramCode || paramCode === localStorage.getItem('userCode');
  useEffect(() => { document.title = user ? `${user.name || 'Profile'} — OIUEEI` : 'Profile — OIUEEI'; }, [user]);

  useEffect(() => {
    if (!localStorage.getItem('userCode')) {
      navigate('/login');
      return;
    }

    if (!userCode) {
      // If no userCode yet, fetch /me to get it
      apiFetch('/api/v1/auth/me/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => {
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        })
        .catch(() => setError('Error loading profile.'));
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await apiFetch(`/api/v1/users/${userCode}/`);
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else if (res.status === 403) {
          setError('You do not have permission to view this profile.');
        } else if (res.status === 404) {
          setError('User not found.');
        } else {
          setError('Error loading profile.');
        }
      } catch {
        setError('Connection error.');
      }
    };
    fetchUser();

    if (isOwnProfile) {
      apiFetch('/api/v1/collections/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => setMyCollections(data.results))
        .catch(() => {});
      apiFetch('/api/v1/invited-collections/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => setInvitedCollections(data))
        .catch(() => {});
    }
  }, [userCode, isOwnProfile, navigate]);

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

  // Use theeeme colors from user data (own profile) or localStorage (other profiles)
  const tc = user.theeeme_colors || (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || {}; } catch { return {}; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
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
          <BackLink to="/" label="Home" />
          <div className="spacer-m" />
          {user.headline && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 500, lineHeight: 'var(--lineheight-s)', color: 'var(--hero-text-color, var(--color-black-90))' }}>{user.headline}</p>}
          <h1 className="form-hero-title">{user.name || user.email}</h1>
          {user.created && (
            <p className="form-hero-text" style={{ fontSize: 'var(--fontsize-body-m)', opacity: 0.7 }}>
              Member since {new Date(user.created).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}
            </p>
          )}
          {isOwnProfile && (
            <div className="button-row-wide" style={{ paddingBottom: 'var(--spacing-s)' }}>
              <Link to="/me/edit">
                <Button style={btnStyle}>Edit profile</Button>
              </Link>
            </div>
          )}
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        {!isOwnProfile && user.shared_collections && user.shared_collections.length > 0 && (
          <>
            <h2>Collections in common</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {user.shared_collections.map((c) => (
                <Linkbox
                  key={c.code}
                  href={`/collections/${c.code}`}
                  onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                  heading={c.headline}
                  linkAriaLabel={`View ${c.headline}`}
                  linkboxAriaLabel={c.headline}
                  border
                  size="small"
                />
              ))}
            </div>
          </>
        )}

        {isOwnProfile && (
          <>
            <h2>My collections</h2>
            <div className="spacer-m" />
            {myCollections === null ? (
              <p className="text-muted">Loading collections...</p>
            ) : myCollections.filter((c) => c.status === 'ACTIVE').length === 0 ? (
              <p>You have no active collections yet. <Link to="/collections/new">Create your first collection</Link> to get started.</p>
            ) : (
              <div className="collections-grid">
                {myCollections.filter((c) => c.status === 'ACTIVE').map((c) => (
                  <Linkbox
                    key={c.code}
                    href={`/collections/${c.code}`}
                    onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                    heading={c.headline}
                    text={`${c.things.length} things · ${c.invites.length} guests`}
                    linkAriaLabel={`View ${c.headline}`}
                    linkboxAriaLabel={c.headline}
                    border
                    size="small"
                  />
                ))}
              </div>
            )}

            {myCollections !== null && myCollections.filter((c) => c.status === 'INACTIVE').length > 0 && (
              <>
                <div className="spacer-xl" />
                <h2>Inactive collections</h2>
                <div className="spacer-m" />
                <div className="collections-grid">
                  {myCollections.filter((c) => c.status === 'INACTIVE').map((c) => (
                    <Linkbox
                      key={c.code}
                      href={`/collections/${c.code}`}
                      onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                      heading={c.headline}
                      text={`${c.things.length} things · ${c.invites.length} guests`}
                      linkAriaLabel={`View ${c.headline}`}
                      linkboxAriaLabel={c.headline}
                      border
                      size="small"
                    />
                  ))}
                </div>
              </>
            )}

            <div className="spacer-xl" />
            <h2>Shared with me</h2>
            <div className="spacer-m" />
            {invitedCollections === null ? (
              <p className="text-muted">Loading collections...</p>
            ) : invitedCollections.length === 0 ? (
              <p>No one has shared a collection with you yet.</p>
            ) : (
              <div className="collections-grid">
                {invitedCollections.map((c) => (
                  <Linkbox
                    key={c.code}
                    href={`/collections/${c.code}`}
                    onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                    heading={c.headline}
                    text={`${c.things.length} things · ${c.invites.length} guests`}
                    linkAriaLabel={`View ${c.headline}`}
                    linkboxAriaLabel={c.headline}
                    border
                    size="small"
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
