import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Notification, Tag } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import placeholderM from '../assets/image-m.png';
import placeholderL from '../assets/image-l.png';
import placeholderXL from '../assets/image-xl.png';

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  const userCode = paramCode || localStorage.getItem('userCode');

  useEffect(() => {
    if (!localStorage.getItem('userCode')) {
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

      <div className="user-profile-header">
        <img
          src={user.hero_url || user.thumbnail_url || placeholderM}
          srcSet={!(user.hero_url || user.thumbnail_url) ? `${placeholderM} 1x, ${placeholderL} 2x, ${placeholderXL} 3x` : undefined}
          alt={user.name || 'Profile'}
          className="user-hero-img"
        />
      </div>

      {user.thumbnail_url && (
        <img
          src={user.thumbnail_url}
          alt={user.name || 'Avatar'}
          className="user-avatar"
        />
      )}

      <h1 className="page-title">{user.name || user.email}</h1>
      {user.headline && <p className="user-headline">{user.headline}</p>}

      {isOwnProfile && (
        <div className="section-mt">
          <Tag>{user.email}</Tag>
        </div>
      )}

      {user.created && (
        <p className="user-meta">
          Member since {new Date(user.created).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}
        </p>
      )}

      {isOwnProfile && (
        <div className="section-mt">
          <Link to="/me/edit">
            <Button>Edit profile</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
