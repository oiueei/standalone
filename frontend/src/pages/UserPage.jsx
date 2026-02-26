import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Notification } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

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
      apiFetch('/api/v1/auth/me/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => {
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        })
        .catch(() => setError('Error loading profile.'));
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await apiFetch(`/api/v1/users/${userCode}/`);
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else if (res.status === 403) {
          setError('You do not have permission to view this profile.');
        } else if (res.status === 404) {
          setError('User not found.');
        } else {
          setError('Error loading profile.');
        }
      } catch {
        setError('Connection error.');
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
    return <LoadingSpinner />;
  }

  const isOwnProfile = !paramCode || paramCode === localStorage.getItem('userCode');

  return (
    <div className="page-container">
      <BackLink to="/" label="Home" />
      <h1 className="page-title">{user.name || user.email}</h1>
      {user.headline && <p>{user.headline}</p>}
      {isOwnProfile && (
        <div style={{ marginTop: '1rem' }}>
          <Link to="/me/edit">
            <Button>Edit profile</Button>
          </Link>
        </div>
      )}
      <pre style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', overflow: 'auto', marginTop: '1rem' }}>
        {JSON.stringify(user, null, 2)}
      </pre>
    </div>
  );
}
