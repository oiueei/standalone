import 'oiueeiDS-design-tokens';
import 'hds-core/lib/fonts/HelsinkiGrotesk.css';
import 'hds-core/lib/base.css';
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import VerifyPage from './pages/VerifyPage';
import HomePage from './pages/HomePage';
import MyCollectionsPage from './pages/MyCollectionsPage';
import InvitedCollectionsPage from './pages/InvitedCollectionsPage';
import CollectionPage from './pages/CollectionPage';
import AddThingPage from './pages/AddThingPage';
import EditThingPage from './pages/EditThingPage';
import ThingPage from './pages/ThingPage';
import CreateCollectionPage from './pages/CreateCollectionPage';
import LogoutPage from './pages/LogoutPage';
import UserPage from './pages/UserPage';
import './App.css';

function App() {
  useEffect(() => {
    fetch('/api/v1/auth/me/', { credentials: 'same-origin' }).catch(() => {});
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/logout" element={<LogoutPage />} />
        <Route path="/verify/:code" element={<VerifyPage />} />
        <Route path="/me" element={<UserPage />} />
        <Route path="/collections" element={<MyCollectionsPage />} />
        <Route path="/collections/new" element={<CreateCollectionPage />} />
        <Route path="/collections/:code" element={<CollectionPage />} />
        <Route path="/collections/:code/add-thing" element={<AddThingPage />} />
        <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
        <Route path="/collections/:code/edit-thing/:thingCode" element={<EditThingPage />} />
        <Route path="/things/:thingCode" element={<ThingPage />} />
        <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="/invited-collections" element={<InvitedCollectionsPage />} />
        <Route path="/:userCode" element={<UserPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
