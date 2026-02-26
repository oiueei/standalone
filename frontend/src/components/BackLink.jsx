import { Link } from 'react-router-dom';

export default function BackLink({ to, label }) {
  return (
    <Link to={to} className="section-mt" style={{ display: 'inline-block' }}>
      &larr; {label}
    </Link>
  );
}
