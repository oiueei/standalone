import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function LogoutPage() {
  const navigate = useNavigate();

  useEffect(() => {
    fetch('/api/v1/auth/logout/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    }).finally(() => {
      localStorage.removeItem('userCode');
      localStorage.removeItem('seenWelcome');
      navigate('/login');
    });
  }, [navigate]);

  return null;
}
