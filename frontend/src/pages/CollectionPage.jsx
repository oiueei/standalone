import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { Button, Linkbox, Notification } from 'hds-react';
import ThingCard from '../components/ThingCard';
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
      {!showWelcome && (
        <Link to="/" style={{ display: 'inline-block', marginBottom: '1rem' }}>
          &larr; Home
        </Link>
      )}
      <img
        src={collection.hero_url || collection.thumbnail_url || placeholderImg}
        alt={collection.headline}
        style={{ width: '100%', maxHeight: '300px', objectFit: 'cover', borderRadius: '8px', marginBottom: '1rem' }}
      />
      <h1 className="page-title">{collection.headline}</h1>
      {collection.description && <p>{collection.description}</p>}
      <p><strong>Estado:</strong> {collection.status}</p>
      <p><strong>Tema:</strong> {collection.theeeme}</p>

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        {isOwner && (
          <Link to={`/collections/${code}/edit`}>
            <Button>Editar coleccion</Button>
          </Link>
        )}
        {isOwner && (
          <Link to={`/collections/${code}/add-thing`}>
            <Button>Anadir cosa</Button>
          </Link>
        )}
        {isOwner && (
          <Link to={`/collections/${code}/invites`}>
            <Button>Gestionar invitados</Button>
          </Link>
        )}
      </div>

      {showWelcome && (
        <Linkbox
          href="/welcome"
          onClick={() => setShowWelcome(false)}
          heading="Welcome to OIUEEI!"
          text="¿quieres saber más? Click aquí"
          linkAriaLabel="Ir a Welcome"
          linkboxAriaLabel="Welcome to OIUEEI!"
          border
        />
      )}

      <h2>Cosas</h2>
      {collection.things.length === 0 ? (
        <p>Sin cosas en esta coleccion.</p>
      ) : (
        <div className="things-grid">
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

    </div>
  );
}
