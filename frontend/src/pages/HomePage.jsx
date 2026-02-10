import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Notification } from 'oiueeiDS-react';

export default function HomePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchMe = async () => {
      try {
        const res = await fetch('/api/v1/auth/me/', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          localStorage.removeItem('token');
          localStorage.removeItem('refresh');
          navigate('/login');
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };
    fetchMe();
  }, [navigate]);

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
      <h1 className="page-title">Hola, {user.name || user.email}</h1>
      <pre style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', overflow: 'auto' }}>
        {JSON.stringify(user, null, 2)}
      </pre>
    </div>
  );
}
