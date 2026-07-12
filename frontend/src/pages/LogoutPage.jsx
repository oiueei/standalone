import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiFetch } from '../services/api';

export default function LogoutPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // apiFetch sends the X-CSRFToken header. The raw fetch this replaced sent none,
    // so the POST was rejected before LogoutView ever ran: the cookies survived and
    // the session came back on the next page load, even though we navigated away.
    apiFetch('/api/v1/auth/logout/', { method: 'POST' }).finally(() => {
      localStorage.removeItem('userCode');
      localStorage.removeItem('seenWelcome');
      navigate('/login');
    });
  }, [navigate]);

  return null;
}
