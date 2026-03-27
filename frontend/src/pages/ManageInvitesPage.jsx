import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TextInput, Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function ManageInvitesPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
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

  const [loading, setLoading] = useState(true);
  const [invites, setInvites] = useState([]);
  const [pendingInvites, setPendingInvites] = useState([]);
  const [collectionHeadline, setCollectionHeadline] = useState('');
  useEffect(() => { document.title = collectionHeadline ? `Guests — ${collectionHeadline} — OIUEEI` : 'Guests — OIUEEI'; }, [collectionHeadline]);
  const [isOwner, setIsOwner] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [resending, setResending] = useState(null);

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchCollection = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setInvites(data.invites || []);
          setPendingInvites(data.pending_invites || []);
          setCollectionHeadline(data.headline || '');
          setIsOwner(localStorage.getItem('userCode') === data.owner);
        } else {
          setToast({ type: 'error', message: 'Error loading collection.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Connection error.' });
      } finally {
        setLoading(false);
      }
    };
    fetchCollection();
  }, [userCode, code, navigate]);

  const handleResend = async (email) => {
    setResending(email);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setToast({ type: 'success', message: 'Invitation resent.' });
      } else {
        setToast({ type: 'error', message: 'Error resending invitation.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setResending(null);
    }
  };

  const handleInvite = async () => {
    setInviteLoading(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail.trim() }),
      });
      if (res.ok) {
        setPendingInvites((prev) => [...prev, { email: inviteEmail.trim() }]);
        setInviteEmail('');
        setToast({ type: 'success', message: 'Invitation sent.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error sending invitation.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setInviteLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

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
          <BackLink to={`/collections/${code}`} label={collectionHeadline || 'Collection'} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">Manage guests</h1>

      {invites.length === 0 && pendingInvites.length === 0 ? (
        <p>No guests.</p>
      ) : (
        <ul className="invite-list">
          {invites.map((invite) => (
            <li key={invite.code} className="invite-row">
              <span>{invite.name || invite.code} ({invite.email})</span>
              {isOwner && (
                <Button
                  variant="danger"
                  onClick={() => navigate(`/collections/${code}/invites/remove`, {
                    state: { guestCode: invite.code, guestName: invite.name || invite.email, backLabel: collectionHeadline || 'Guests' },
                  })}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
          {pendingInvites.map((pending) => (
            <li key={pending.code || pending.email} className="invite-row">
              <span>{pending.email} <em className="text-muted">Pending</em></span>
              {isOwner && (
                <div className="button-row">
                  <Button
                    variant="secondary"
                    style={btnSecondaryStyle}
                    disabled={resending === pending.email}
                    onClick={() => handleResend(pending.email)}
                  >
                    {resending === pending.email ? 'Sending...' : 'Resend'}
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => navigate(`/collections/${code}/invites/remove`, {
                      state: { guestCode: pending.code, guestName: pending.email, backLabel: collectionHeadline || 'Guests' },
                    })}
                  >
                    Remove
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {isOwner && (
        <div className="form-grid section-mt">
          <TextInput
            id="manage-invites-email"
            label="Guest email"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@email.com"
          />
          <Button
            disabled={inviteLoading || !inviteEmail.trim()}
            onClick={handleInvite}
            className="fit-content"
            style={btnStyle}
          >
            {inviteLoading ? 'Sending...' : 'Invite'}
          </Button>
        </div>
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
