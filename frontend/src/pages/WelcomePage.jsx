import { Link } from 'react-router-dom';
import { Button } from 'hds-react';
import BackLink from '../components/BackLink';

export default function WelcomePage() {
  return (
    <div className="page-container">
      <BackLink to="/" label="Home" />
      <h1 className="page-title">Welcome to OIUEEI!</h1>
      <p>
        OIUEEI is an open-source web application that lets people share their belongings with
        friends and others around. Users can create collections (wishlists, gift lists, items for
        sale) and share them with friends who can then reserve items or ask questions.
      </p>
      <div className="button-row section-mt">
        <Link to="/collections/new" state={{ backPath: '/welcome', backLabel: 'Welcome' }}>
          <Button>Create collection</Button>
        </Link>
        <Link to="/me/edit" state={{ backPath: '/welcome', backLabel: 'Welcome' }}>
          <Button variant="secondary">Edit profile</Button>
        </Link>
      </div>
    </div>
  );
}
