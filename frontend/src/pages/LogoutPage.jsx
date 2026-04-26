import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { resetAnalytics } from '../services/analytics';

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
      resetAnalytics();
      navigate('/login');
    });
  }, [navigate]);

  return null;
}
