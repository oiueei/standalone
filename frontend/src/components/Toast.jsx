import { Notification } from 'hds-react';

export default function Toast({ toast, onClose }) {
  if (!toast) return null;

  return (
    <Notification
      label={toast.type === 'success' ? 'Done' : 'Error'}
      type={toast.type}
      position="top-right"
      autoClose
      dismissible
      closeButtonLabelText="Close"
      onClose={onClose}
    >
      {toast.message}
    </Notification>
  );
}
