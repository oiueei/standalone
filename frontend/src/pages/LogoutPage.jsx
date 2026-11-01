import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';

import { apiFetch } from '../services/api';

export default function LogoutPage() {
  const navigate = useNavigate();
  // The session ends once per visit: going to the login changes the address while this
  // page is still mounted, and `navigate` with it, which re-ran the effect and posted again.
  const endedRef = useRef(false);

  useEffect(() => {
    if (endedRef.current) return;
    endedRef.current = true;
    // apiFetch sends the X-CSRFToken header. The raw fetch this replaced sent none,
    // so the POST was rejected before LogoutView ever ran: the cookies survived and
    // the session came back on the next page load, even though we navigated away.
    apiFetch('/api/v1/auth/logout/', { method: 'POST' }).finally(() => {
      localStorage.removeItem('userCode');
      navigate('/login');
    });
    // `navigate` is not a dependency, on purpose: see `endedRef`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
