import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { StepByStep, TextInput, Button, Notification } from 'hds-react';

export default function ManageInvitesPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [invites, setInvites] = useState([]);
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
          setCollectionHeadline(data.headline || '');
          setIsOwner(localStorage.getItem('userCode') === data.owner);
        } else {
          setToast({ type: 'error', message: 'Error al cargar la coleccion.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Error de conexion.' });
      } finally {
        setLoading(false);
      }
    };
    fetchCollection();
  }, [token, code, navigate]);

  const handleRemove = async (userCode) => {
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
        setInvites((prev) => prev.filter((c) => c !== userCode));
        setToast({ type: 'success', message: 'Invitado eliminado.' });
      } else {
        setToast({ type: 'error', message: 'Error al eliminar invitado.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
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
        setInvites((prev) => [...prev, data.user_code]);
        setInviteEmail('');
        setToast({ type: 'success', message: 'Invitacion enviada.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error al enviar la invitacion.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
    } finally {
      setInviteLoading(false);
    }
  };

  if (loading) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  const steps = [
    {
      title: 'Invitados actuales',
      description: (
        <div>
          {invites.length === 0 ? (
            <p>Sin invitados.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.5rem' }}>
              {invites.map((inviteCode) => (
                <li key={inviteCode} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{inviteCode}</span>
                  {isOwner && (
                    <Button
                      variant="danger"

                      onClick={() => handleRemove(inviteCode)}
                    >
                      Eliminar
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
      title: 'Invitar',
      description: isOwner ? (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Email del invitado"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="usuario@email.com"
          />
          <Button
            disabled={inviteLoading || !inviteEmail.trim()}
            onClick={handleInvite}
            style={{ width: 'fit-content' }}
          >
            {inviteLoading ? 'Enviando...' : 'Invitar'}
          </Button>
        </div>
      ) : (
        <p>Solo el propietario puede invitar usuarios.</p>
      ),
    },
  ];

  return (
    <div className="page-container">
      <Link to={`/collections/${code}`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {collectionHeadline || 'Colección'}
      </Link>
      <StepByStep title="Gestionar invitados" steps={steps} numberedList />

      {toast && (
        <Notification
          label={toast.type === 'success' ? 'Listo' : 'Error'}
          type={toast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Cerrar"
          onClose={() => setToast(null)}
        >
          {toast.message}
        </Notification>
      )}
    </div>
  );
}
