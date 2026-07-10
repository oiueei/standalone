import { Link } from 'react-router-dom';
import { IconArrowLeft } from 'hds-react';

export default function BackLink({ to, label }) {
  return (
    <Link to={to} className="back-link section-mt">
      <IconArrowLeft aria-hidden="true" /> {label}
    </Link>
  );
}
