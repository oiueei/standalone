import { LoadingSpinner as HdsSpinner } from 'hds-react';

export default function LoadingSpinner() {
  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
        <HdsSpinner />
      </div>
    </div>
  );
}
