import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { StepByStep, TextInput, Button, Dialog } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function ManageInvitesPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [invites, setInvites] = useState([]);
  const [pendingInvites, setPendingInvites] = useState([]);
  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [isOwner, setIsOwner] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null);

  useEffect(() => {
    if (!token) {
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
  }, [token, code, navigate]);

  const handleRemove = async (userCode, isPending = false) => {
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'DELETE',
        body: JSON.stringify({ user_code: userCode }),
      });
      if (res.ok) {
        if (isPending) {
          setPendingInvites((prev) => prev.filter((inv) => inv.code !== userCode));
        } else {
          setInvites((prev) => prev.filter((inv) => inv.code !== userCode));
        }
        setToast({ type: 'success', message: 'Guest removed.' });
      } else {
        setToast({ type: 'error', message: 'Error removing guest.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
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
        const data = await res.json();
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

  const steps = [
    {
      title: 'Current guests',
      description: (
        <div>
          {invites.length === 0 && pendingInvites.length === 0 ? (
            <p>No guests.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.5rem' }}>
              {invites.map((invite) => (
                <li key={invite.code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{invite.name || invite.code} ({invite.email})</span>
                  {isOwner && (
                    <Button
                      variant="danger"
                      onClick={() => setConfirmRemove({ code: invite.code, name: invite.name || invite.email, isPending: false })}
                    >
                      Remove
                    </Button>
                  )}
                </li>
              ))}
              {pendingInvites.map((pending) => (
                <li key={pending.code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{pending.email} <em style={{ color: '#666' }}>Pending</em></span>
                  {isOwner && (
                    <Button
                      variant="danger"
                      onClick={() => setConfirmRemove({ code: pending.code, name: pending.email, isPending: true })}
                    >
                      Remove
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ),
    },
    {
      title: 'Invite',
      description: isOwner ? (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Guest email"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@email.com"
          />
          <Button
            disabled={inviteLoading || !inviteEmail.trim()}
            onClick={handleInvite}
            style={{ width: 'fit-content' }}
          >
            {inviteLoading ? 'Sending...' : 'Invite'}
          </Button>
        </div>
      ) : (
        <p>Only the owner can invite users.</p>
      ),
    },
  ];

  return (
    <div className="page-container">
      <BackLink to={`/collections/${code}`} label={collectionHeadline || 'Collection'} />
      <StepByStep title="Manage guests" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
      <Dialog
        id="confirm-remove-guest"
        aria-labelledby="confirm-remove-guest-header"
        isOpen={!!confirmRemove}
        close={() => setConfirmRemove(null)}
        closeButtonLabelText="Cancel"
        theme={{ '--accent-line-color': 'var(--color-error)' }}
      >
        <Dialog.Header id="confirm-remove-guest-header" title="Remove guest?" />
        <Dialog.Content>
          <p>Are you sure you want to remove <strong>{confirmRemove?.name}</strong> from this collection?</p>
        </Dialog.Content>
        <Dialog.ActionButtons>
          <Button variant="danger" onClick={() => { const { code: c, isPending } = confirmRemove; setConfirmRemove(null); handleRemove(c, isPending); }}>
            Remove
          </Button>
          <Button variant="secondary" onClick={() => setConfirmRemove(null)}>
            Cancel
          </Button>
        </Dialog.ActionButtons>
      </Dialog>
    </div>
  );
}
