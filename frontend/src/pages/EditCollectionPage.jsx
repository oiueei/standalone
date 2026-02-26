import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Select, Button } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

const STATUS_OPTIONS = [
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Inactive', value: 'INACTIVE' },
];

export default function EditCollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [hero, setHero] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const collectionRes = await apiFetch(`/api/v1/collections/${code}/`);

        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setHero(data.hero || '');
          setStatus(data.status || 'ACTIVE');
        } else {
          setToast({ type: 'error', message: 'Error loading collection.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Connection error.' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token, code, navigate]);

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

    const body = {
      headline: headline.trim(),
      description: description.trim(),
      thumbnail: thumbnail.trim(),
      hero: hero.trim(),
      status,
    };

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
      } else {
        const data = await res.json().catch(() => ({}));
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error saving.';
        setToast({ type: 'error', message });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="page-container"><p>Loading...</p></div>;
  }

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
          <Select
            label="Status"
            options={STATUS_OPTIONS}
            value={status}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                setStatus(selectedOptions[0].value);
              }
            }}
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
            <dt><strong>Status</strong></dt>
            <dd>{status === 'ACTIVE' ? 'Active' : 'Inactive'}</dd>
          </dl>
          <div style={{ marginTop: '1rem' }}>
            <Button disabled={submitting} onClick={handleSubmit}>
              {submitting ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <BackLink to={`/collections/${code}`} label={headline || 'Collection'} />
      <StepByStep title="Edit collection" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
