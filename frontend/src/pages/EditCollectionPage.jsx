import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TextInput, TextArea, Select, Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

const STATUS_OPTIONS = [
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Inactive', value: 'INACTIVE' },
];

export default function EditCollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  useEffect(() => { document.title = headline ? `Edit ${headline} — OIUEEI` : 'Edit collection — OIUEEI'; }, [headline]);
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!userCode) {
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
  }, [userCode, code, navigate]);

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
    return <LoadingSpinner />;
  }

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <BackLink to={`/collections/${code}`} label={headline || 'Collection'} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">Edit collection</h1>
      <div className="form-grid">
        <TextInput
          id="edit-collection-headline"
          label="Title"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={`${headline.length}/64`}
        />
        <TextArea
          id="edit-collection-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          helperText={`${description.length}/256`}
        />
        <Select
          id="edit-collection-status"
          texts={{ label: 'Status' }}
          helper="Inactive collections are visible to guests but reservations are paused."
          options={STATUS_OPTIONS}
          value={status}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setStatus(selectedOptions[0].value);
            }
          }}
        />
      </div>
      <div className="form-actions">
        <Button disabled={submitting} onClick={handleSubmit} style={{ ...btnStyle, width: '100%' }}>
          {submitting ? 'Saving...' : 'Save'}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
