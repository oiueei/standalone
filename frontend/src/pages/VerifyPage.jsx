import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Notification } from 'hds-react';

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.action === 'COLLECTION_REJECT') {
          setSuccess('Invitation declined. The collection owner has been notified.');
        } else if (res.ok && data.action === 'BOOKING_ACCEPT') {
          setSuccess('The hold has been confirmed!');
        } else if (res.ok && data.action === 'BOOKING_REJECT') {
          setSuccess('The hold has been rejected.');
        } else if (res.ok && data.user) {
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          if (data.invited_collection) {
            navigate(`/collections/${data.invited_collection}`, { state: { fromInvite: true } });
          } else {
            navigate('/');
          }
        } else {
          setError(data.error || 'Invalid or expired link.');
        }
      } catch {
        setError('Connection error.');
      }
    };
    verify();
  }, [code, navigate]);

  if (success) {
    return (
      <div className="page-container">
        <Notification label="Done" type="success">
          {success}
        </Notification>
        <div className="section-mt">
          <Link to="/login">
            <Button variant="secondary">Go to login</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">
          {error}
        </Notification>
        <p className="section-mt">
          If your link has expired, ask the person who invited you to send a new one, or request a new magic link.
        </p>
        <div className="section-mt">
          <Link to="/login">
            <Button variant="secondary">Go to login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <p>Verifying...</p>
    </div>
  );
}
