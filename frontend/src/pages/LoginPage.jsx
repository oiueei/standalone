import { useState } from 'react';
import { TextInput, Button, Notification } from 'oiueeiDS-react';

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null); // 'success' | 'alert' | 'error'
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus(null);
    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/request-link/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus('success');
        setMessage('Enlace enviado. Revisa tu correo.');
      } else if (res.status === 404) {
        setStatus('alert');
        setMessage(data.error || 'No existe una cuenta con ese email.');
      } else {
        setStatus('error');
        setMessage(data.error || data.detail || 'Error al enviar el enlace.');
      }
    } catch {
      setStatus('error');
      setMessage('Error de conexion con el servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title">OIUEEI</h1>

      {status ? (
        <Notification label={status === 'success' ? 'Enviado' : status === 'alert' ? 'Aviso' : 'Error'} type={status}>
          {message}
        </Notification>
      ) : (
        <form onSubmit={handleSubmit} style={{ maxWidth: '400px' }}>
          <TextInput
            id="login-email"
            label="Email"
            type="email"
            placeholder="tu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ marginBottom: '1rem' }}
          />
          <Button type="submit" disabled={loading}>
            {loading ? 'Enviando...' : 'Enviar enlace de acceso'}
          </Button>
        </form>
      )}
    </div>
  );
}
