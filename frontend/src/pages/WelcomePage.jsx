import { Link } from 'react-router-dom';

export default function WelcomePage() {
  return (
    <div className="page-container">
      <Link to={-1} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; Volver
      </Link>
      <h1 className="page-title">Welcome to OIUEEI!</h1>
      <p>
        OIUEEI is an open-source web application that lets people share their belongings with
        friends and others around. Users can create collections (wishlists, gift lists, items for
        sale) and share them with friends who can then reserve items or ask questions.
      </p>
    </div>
  );
}
