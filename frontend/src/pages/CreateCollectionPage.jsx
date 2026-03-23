import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TextInput, TextArea, Button } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function CreateCollectionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Home';
  const userCode = localStorage.getItem('userCode');

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'Title is required.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = { headline: headline.trim() };
    if (description.trim()) body.description = description.trim();

    try {
      const res = await apiFetch('/api/v1/collections/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        navigate(`/collections/${data.code}`);
      } else {
        const data = await res.json().catch(() => ({}));
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error creating collection.';
        setToast({ type: 'error', message });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-container">
      <BackLink to={backPath} label={backLabel} />
      <h1 className="page-title">Create collection</h1>
      <div className="form-grid">
        <TextInput
          id="create-collection-headline"
          label="Title"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={`${headline.length}/64`}
        />
        <TextArea
          id="create-collection-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="section-mt">
        <Button disabled={submitting} onClick={handleSubmit}>
          {submitting ? 'Creating...' : 'Create'}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
