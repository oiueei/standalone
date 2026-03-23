import { useState } from 'react';
import { TextInput, Button, Notification } from 'hds-react';
import { getCsrfToken } from '../services/api';

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
        setMessage(data.message || 'If this email is registered, a magic link has been sent.');
      } else {
        setStatus('error');
        setMessage(data.error || data.detail || 'Error sending link.');
      }
    } catch {
      setStatus('error');
      setMessage('Connection error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title">OIUEEI</h1>

      {status ? (
        <Notification label={status === 'success' ? 'Sent' : status === 'alert' ? 'Warning' : 'Error'} type={status}>
          {message}
        </Notification>
      ) : (
        <form onSubmit={handleSubmit} style={{ maxWidth: '400px' }}>
          <TextInput
            id="login-email"
            label="Email"
            type="email"
            placeholder="you@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="section-mt"
          />
          <div className="section-mt">
            <Button type="submit" disabled={loading}>
              {loading ? 'Sending...' : 'Sign in'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
