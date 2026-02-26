import { Link } from 'react-router-dom';

export default function BackLink({ to, label }) {
  return (
    <Link to={to} style={{ display: 'inline-block', marginBottom: '1rem' }}>
      &larr; {label}
    </Link>
  );
}
