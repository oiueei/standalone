import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Notification } from 'oiueeiDS-react';

export default function InvitedCollectionsPage() {
  const navigate = useNavigate();
  const [collections, setCollections] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchCollections = async () => {
      try {
        const res = await fetch('/api/v1/invited-collections/', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.status === 401) {
          localStorage.removeItem('token');
          localStorage.removeItem('refresh');
          navigate('/login');
          return;
        }
        if (!res.ok) {
          setError('Error al cargar las colecciones invitadas.');
          return;
        }
        const data = await res.json();
        setCollections(data);
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };
    fetchCollections();
  }, [navigate]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!collections) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  return (
    <div className="page-container">
      <h1 className="page-title">Colecciones invitadas</h1>
      {collections.length === 0 ? (
        <p>No tienes invitaciones a colecciones.</p>
      ) : (
        <ul>
          {collections.map((c) => (
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
    </div>
  );
}
