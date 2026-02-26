import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Button } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function CreateCollectionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Home';
  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [hero, setHero] = useState('');
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
    if (thumbnail.trim()) body.thumbnail = thumbnail.trim();
    if (hero.trim()) body.hero = hero.trim();

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

  const steps = [
    {
      title: 'Details',
      description: (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Title"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            required
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextArea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <TextInput
            label="Thumbnail (Cloudinary ID)"
            value={thumbnail}
            onChange={(e) => setThumbnail(e.target.value)}
          />
          <TextInput
            label="Hero (Cloudinary ID)"
            value={hero}
            onChange={(e) => setHero(e.target.value)}
          />
        </div>
      ),
    },
    {
      title: 'Summary',
      description: (
        <div>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Title</strong></dt>
            <dd>{headline || '—'}</dd>
            {description && (
              <>
                <dt><strong>Description</strong></dt>
                <dd>{description}</dd>
              </>
            )}
            <dt><strong>Thumbnail</strong></dt>
            <dd>{thumbnail || '—'}</dd>
            <dt><strong>Hero</strong></dt>
            <dd>{hero || '—'}</dd>
          </dl>
          <div style={{ marginTop: '1rem' }}>
            <Button disabled={submitting} onClick={handleSubmit}>
              {submitting ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <BackLink to={backPath} label={backLabel} />
      <StepByStep title="Create collection" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
