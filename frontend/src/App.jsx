import 'oiueeiDS-design-tokens';
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import VerifyPage from './pages/VerifyPage';
import HomePage from './pages/HomePage';
import MyCollectionsPage from './pages/MyCollectionsPage';
import InvitedCollectionsPage from './pages/InvitedCollectionsPage';
import CollectionPage from './pages/CollectionPage';
import UserPage from './pages/UserPage';
import './App.css';

function App() {
  useEffect(() => {
    fetch('/api/v1/auth/me/', { credentials: 'same-origin' }).catch(() => {});
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify/:code" element={<VerifyPage />} />
        <Route path="/me" element={<HomePage />} />
        <Route path="/collections" element={<MyCollectionsPage />} />
        <Route path="/collections/:code" element={<CollectionPage />} />
        <Route path="/invited-collections" element={<InvitedCollectionsPage />} />
        <Route path="/:userCode" element={<UserPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
