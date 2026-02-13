import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Notification } from 'oiueeiDS-react';

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  const userCode = paramCode || localStorage.getItem('userCode');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    if (!userCode) {
      // If no userCode yet, fetch /me to get it
      fetch('/api/v1/auth/me/', { headers: { 'Authorization': `Bearer ${token}` } })
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => {
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        })
        .catch(() => setError('Error al cargar el perfil.'));
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await fetch(`/api/v1/users/${userCode}/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else if (res.status === 403) {
          setError('No tienes permiso para ver este perfil.');
        } else if (res.status === 404) {
          setError('Usuario no encontrado.');
        } else {
          setError('Error al cargar el perfil.');
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };
    fetchUser();
  }, [userCode, navigate]);

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

  return (
    <div className="page-container">
      <h1 className="page-title">{user.name || user.email}</h1>
      <pre style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', overflow: 'auto' }}>
        {JSON.stringify(user, null, 2)}
      </pre>
    </div>
  );
}
