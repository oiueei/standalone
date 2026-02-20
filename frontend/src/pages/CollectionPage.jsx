import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Dialog, Notification, TextInput } from 'hds-react';
import ThingCard from '../components/ThingCard';

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteToast, setInviteToast] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
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
          setCollection(data);
        } else if (res.status === 403) {
          setError('No tienes permiso para ver esta coleccion.');
        } else if (res.status === 404) {
          setError('Coleccion no encontrada.');
        } else {
          setError('Error al cargar la coleccion.');
        }
      } catch {
        setError('Error de conexion con el servidor.');
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
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  const isOwner = localStorage.getItem('userCode') === collection.owner;

  return (
    <div className="page-container">
      <h1 className="page-title">{collection.headline}</h1>
      <p><strong>Estado:</strong> {collection.status}</p>
      {collection.description && <p>{collection.description}</p>}
      <p><strong>Tema:</strong> {collection.theeeme}</p>

      {isOwner && (
        <Link to={`/collections/${code}/add-thing`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
          <Button>Anadir cosa</Button>
        </Link>
      )}

      <h2>Cosas ({collection.things.length})</h2>
      {collection.things.length === 0 ? (
        <p>Sin cosas en esta coleccion.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {[...collection.things].sort((a, b) => new Date(b.created) - new Date(a.created)).map((thing) => (
            <ThingCard
              key={thing.code}
              thing={thing}
              userCode={localStorage.getItem('userCode')}
              collectionCode={code}
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

      <h2>
        <a href="#" onClick={(e) => { e.preventDefault(); setDialogOpen(true); }} style={{ color: 'inherit' }}>
          Invitados ({collection.invites.length})
        </a>
      </h2>

      <Dialog
        id="invites-dialog"
        isOpen={dialogOpen}
        aria-labelledby="invites-dialog-title"
        close={() => setDialogOpen(false)}
        closeButtonLabelText="Cerrar"
        scrollable
      >
        <Dialog.Header id="invites-dialog-title" title="Invitados" />
        <Dialog.Content>
          {collection.invites.length === 0 ? (
            <p>Sin invitados.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.5rem' }}>
              {collection.invites.map((inviteCode) => (
                <li key={inviteCode} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{inviteCode}</span>
                  {isOwner && (
                    <Button
                      variant="danger"
                      size="small"
                      onClick={async () => {
                        const token = localStorage.getItem('token');
                        try {
                          const res = await fetch(`/api/v1/collections/${code}/invite/`, {
                            method: 'DELETE',
                            headers: {
                              'Authorization': `Bearer ${token}`,
                              'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ user_code: inviteCode }),
                          });
                          if (res.ok) {
                            setCollection((prev) => ({
                              ...prev,
                              invites: prev.invites.filter((c) => c !== inviteCode),
                            }));
                          } else {
                            setInviteToast({ type: 'error', message: 'Error al eliminar invitado.' });
                          }
                        } catch {
                          setInviteToast({ type: 'error', message: 'Error de conexion.' });
                        }
                      }}
                    >
                      Eliminar
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {isOwner && (
            <div style={{ marginTop: '1rem', display: 'grid', gap: '0.5rem' }}>
              <TextInput
                label="Email del invitado"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="usuario@email.com"
              />
              <Button
                disabled={inviteLoading || !inviteEmail.trim()}
                onClick={async () => {
                  const token = localStorage.getItem('token');
                  setInviteLoading(true);
                  setInviteToast(null);
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
                      setCollection((prev) => ({
                        ...prev,
                        invites: [...prev.invites, data.user_code],
                      }));
                      setInviteEmail('');
                      setInviteToast({ type: 'success', message: 'Invitacion enviada.' });
                    } else {
                      const data = await res.json().catch(() => ({}));
                      setInviteToast({ type: 'error', message: data.detail || 'Error al enviar la invitacion.' });
                    }
                  } catch {
                    setInviteToast({ type: 'error', message: 'Error de conexion.' });
                  } finally {
                    setInviteLoading(false);
                  }
                }}
              >
                {inviteLoading ? 'Enviando...' : 'Invitar'}
              </Button>
            </div>
          )}
        </Dialog.Content>
      </Dialog>

      {inviteToast && (
        <Notification
          label={inviteToast.type === 'success' ? 'Listo' : 'Error'}
          type={inviteToast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Cerrar"
          onClose={() => setInviteToast(null)}
        >
          {inviteToast.message}
        </Notification>
      )}
    </div>
  );
}
