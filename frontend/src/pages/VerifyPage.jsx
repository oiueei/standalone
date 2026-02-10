import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Notification } from 'oiueeiDS-react';

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.token) {
          localStorage.setItem('token', data.token);
          localStorage.setItem('refresh', data.refresh);
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          navigate('/me');
        } else {
          setError(data.error || 'Enlace no valido o expirado.');
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };
    verify();
  }, [code, navigate]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">
          {error}
        </Notification>
      </div>
    );
  }

  return (
    <div className="page-container">
      <p>Verificando...</p>
    </div>
  );
}
