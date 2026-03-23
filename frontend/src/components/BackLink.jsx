import { Link } from 'react-router-dom';

export default function BackLink({ to, label }) {
  return (
    <Link to={to} className="back-link section-mt">
      &larr; {label}
    </Link>
  );
}
