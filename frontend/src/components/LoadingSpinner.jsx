import { LoadingSpinner as HdsSpinner } from 'hds-react';

export default function LoadingSpinner() {
  return (
    <div className="page-container">
      <div className="spinner-container">
        <HdsSpinner />
      </div>
    </div>
  );
}
