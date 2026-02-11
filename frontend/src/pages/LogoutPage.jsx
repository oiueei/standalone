import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function LogoutPage() {
  const navigate = useNavigate();

  useEffect(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh');
    localStorage.removeItem('userCode');
    navigate('/login');
  }, [navigate]);

  return null;
}
