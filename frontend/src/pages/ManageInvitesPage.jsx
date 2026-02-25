import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { StepByStep, TextInput, Button, Notification } from 'hds-react';

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

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchCollection = async () => {
      try {
        const res = await fetch(`/api/v1/collections/${code}/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
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
      const res = await fetch(`/api/v1/collections/${code}/invite/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
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
      const res = await fetch(`/api/v1/collections/${code}/invite/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
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
    return <div className="page-container"><p>Loading...</p></div>;
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
                      onClick={() => handleRemove(invite.code)}
                    >
                      Delete
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
                      onClick={() => handleRemove(pending.code, true)}
                    >
                      Delete
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
      <Link to={`/collections/${code}`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {collectionHeadline || 'Collection'}
      </Link>
      <StepByStep title="Manage guests" steps={steps} numberedList />

      {toast && (
        <Notification
          label={toast.type === 'success' ? 'Done' : 'Error'}
          type={toast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Close"
          onClose={() => setToast(null)}
        >
          {toast.message}
        </Notification>
      )}
    </div>
  );
}
