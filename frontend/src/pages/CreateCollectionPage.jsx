import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TextInput, TextArea, Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function CreateCollectionPage() {
  const navigate = useNavigate();
  useEffect(() => { document.title = 'New collection — OIUEEI'; }, []);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Home';
  const userCode = localStorage.getItem('userCode');
  const theeemeColors = JSON.parse(localStorage.getItem('theeemeColors') || '{}');

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
    <div
      className="form-page"
      style={theeemeColors.color_02 ? { backgroundColor: `var(--color-${theeemeColors.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={theeemeColors.color_03 ? { backgroundColor: `var(--color-${theeemeColors.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={theeemeColors.color_04 ? { '--hero-text-color': `var(--color-${theeemeColors.color_04})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={theeemeColors.color_02 ? { fill: `var(--color-${theeemeColors.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">Create collection</h1>
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
            helperText={`${description.length}/256`}
          />
        </div>
        <div className="form-actions">
          <Button
            fullWidth
            disabled={submitting}
            onClick={handleSubmit}
            style={theeemeColors.color_01 ? {
              '--background-color': `var(--color-${theeemeColors.color_01})`,
              '--background-color-hover': `var(--color-${theeemeColors.color_01}-dark)`,
              '--color': theeemeColors.color_05 ? `var(--color-${theeemeColors.color_05})` : 'var(--color-white)',
              '--border-color': `var(--color-${theeemeColors.color_01})`,
            } : undefined}
          >
            {submitting ? 'Creating...' : 'Create'}
          </Button>
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
