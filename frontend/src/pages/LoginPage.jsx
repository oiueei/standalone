import { useEffect, useState } from 'react';
import { TextInput, Button, Notification, Koros } from 'hds-react';
import { getCsrfToken } from '../services/api';

export default function LoginPage() {
  useEffect(() => { document.title = 'Sign in — OIUEEI'; }, []);
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

  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || {}; } catch { return {}; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <h1 className="form-hero-title">OIUEEI</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
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
            <div className="spacer-m"></div>
            <div className="section-mt">
              <Button type="submit" fullWidth disabled={loading} style={btnStyle}>
                {loading ? 'Sending...' : 'Sign in'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
