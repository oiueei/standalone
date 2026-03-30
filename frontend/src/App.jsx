import './i18n';
import 'hds-design-tokens';
import 'hds-core/lib/base.css';
import './fonts/oiueei-fonts.css';
import './styles/oiueei-theme.css';
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import VerifyPage from './pages/VerifyPage';
import HomePage from './pages/HomePage';
import CollectionPage from './pages/CollectionPage';
import AddThingPage from './pages/AddThingPage';
import EditThingPage from './pages/EditThingPage';
import ThingPage from './pages/ThingPage';
import CreateCollectionPage from './pages/CreateCollectionPage';
import EditCollectionPage from './pages/EditCollectionPage';
import EditProfilePage from './pages/EditProfilePage';
import ManageInvitesPage from './pages/ManageInvitesPage';
import LogoutPage from './pages/LogoutPage';
import UserPage from './pages/UserPage';
import RequestThingPage from './pages/RequestThingPage';
import DeleteThingPage from './pages/DeleteThingPage';
import RemoveGuestPage from './pages/RemoveGuestPage';
import MyBookingsPage from './pages/MyBookingsPage';
import WelcomePage from './pages/WelcomePage';
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
        <Route path="/rsvp/:code" element={<VerifyPage />} />
        <Route path="/me" element={<UserPage />} />
        <Route path="/me/edit" element={<EditProfilePage />} />
        <Route path="/collections/new" element={<CreateCollectionPage />} />
        <Route path="/collections/:code" element={<CollectionPage />} />
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        <Route path="/collections/:code/invites" element={<ManageInvitesPage />} />
        <Route path="/collections/:code/add" element={<AddThingPage />} />
        <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
        <Route path="/collections/:code/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="/collections/:code/things/:thingCode/delete" element={<DeleteThingPage />} />
        <Route path="/collections/:code/invites/remove" element={<RemoveGuestPage />} />
        <Route path="/things/:thingCode" element={<ThingPage />} />
        <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="/things/:thingCode/delete" element={<DeleteThingPage />} />
        <Route path="/my-bookings" element={<MyBookingsPage />} />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/:userCode" element={<UserPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
