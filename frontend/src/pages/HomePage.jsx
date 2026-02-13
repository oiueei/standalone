import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Notification } from 'oiueeiDS-react';
import ThingCard from '../components/ThingCard';

export default function HomePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [myCollectionsCount, setMyCollectionsCount] = useState(null);
  const [invitedCollectionsCount, setInvitedCollectionsCount] = useState(null);
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
          setMyCollectionsCount(data.results.length);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await fetch('/api/v1/invited-collections/', { headers });
        if (res.status === 401) { handleUnauth(); return; }
        if (res.ok) {
          const data = await res.json();
          setInvitedCollectionsCount(data.length);
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
      <h1 className="page-title">Hola, {user.name || user.email}</h1>

      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', marginBottom: '1.5rem' }}>
        <Link to="/collections">
          Mis colecciones ({myCollectionsCount ?? '...'})
        </Link>
        <Link to="/invited-collections">
          Colecciones invitadas ({invitedCollectionsCount ?? '...'})
        </Link>
        <Link to="/collections/new">
          <Button size="small">Crear coleccion</Button>
        </Link>
      </div>

      <h2>Todas las cosas ({allThings.length})</h2>
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
