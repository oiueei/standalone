import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Notification } from 'hds-react';
import ThingCard from '../components/ThingCard';
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

    const headers = { 'Authorization': `Bearer ${token}` };

    const handleUnauth = () => {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh');
      navigate('/login');
    };

    const fetchMe = async () => {
      try {
        const res = await fetch('/api/v1/auth/me/', { headers });
        if (res.ok) {
          const data = await res.json();
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        } else {
          handleUnauth();
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };

    const fetchMyCollections = async () => {
      try {
        const res = await fetch('/api/v1/collections/', { headers });
        if (res.status === 401) { handleUnauth(); return; }
        if (res.ok) {
          const data = await res.json();
          setMyCollections(data.results);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await fetch('/api/v1/invited-collections/', { headers });
        if (res.status === 401) { handleUnauth(); return; }
        if (res.ok) {
          const data = await res.json();
          setInvitedCollections(data);
        }
      } catch { /* silently fail */ }
    };

    const fetchMyThings = async () => {
      try {
        const res = await fetch('/api/v1/things/', { headers });
        if (res.status === 401) { handleUnauth(); return; }
        if (res.ok) {
          const data = await res.json();
          setMyThings(data.results);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedThings = async () => {
      try {
        const res = await fetch('/api/v1/invited-things/', { headers });
        if (res.status === 401) { handleUnauth(); return; }
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
    return <div className="page-container"><p>Cargando...</p></div>;
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
      <h1 className="page-title">Hola, {user.name || user.email}</h1>
      {user.headline && <p>{user.headline}</p>}

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <Link to="/collections/new">
          <Button>Crear coleccion</Button>
        </Link>
        <Link to="/me/edit">
          <Button>Editar perfil</Button>
        </Link>
      </div>

      <h2>Mis colecciones</h2>
      {myCollections === null ? (
        <p>Cargando...</p>
      ) : myCollections.length === 0 ? (
        <p>No tienes colecciones.</p>
      ) : (
        <ul>
          {myCollections.map((c) => (
            <li key={c.code}>
              <Link to={`/collections/${c.code}`}>
                <strong>{c.headline}</strong>
              </Link>
              {' — '}
              {c.status} · {c.things.length} cosas · {c.invites.length} invitados
            </li>
          ))}
        </ul>
      )}

      <h2>Colecciones invitadas</h2>
      {invitedCollections === null ? (
        <p>Cargando...</p>
      ) : invitedCollections.length === 0 ? (
        <p>No tienes invitaciones a colecciones.</p>
      ) : (
        <ul>
          {invitedCollections.map((c) => (
            <li key={c.code}>
              <Link to={`/collections/${c.code}`}>
                <strong>{c.headline}</strong>
              </Link>
              {' — '}
              {c.status} · {c.things.length} cosas · {c.invites.length} invitados
            </li>
          ))}
        </ul>
      )}

      <h2>Todas las cosas</h2>
      {myThings === null || invitedThings === null ? (
        <p>Cargando...</p>
      ) : allThings.length === 0 ? (
        <p>No tienes cosas.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {allThings.map((thing) => (
            <ThingCard
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
