import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Select,
  StepByStep,
  TextInput,
  TextArea,
  NumberInput,
  Button,
} from 'hds-react';
import { TYPE_OPTIONS, TYPE_LABELS, FEE_TYPES } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function EditThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [thingType, setThingType] = useState('');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [pictures, setPictures] = useState('');
  const [fee, setFee] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState(null);
  const [thingCollectionCode, setThingCollectionCode] = useState(code || '');
  const [thingCollectionHeadline, setThingCollectionHeadline] = useState('');

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    const fetchThing = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/`);
        if (res.ok) {
          const data = await res.json();
          setThingType(data.type);
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setPictures((data.pictures || []).join(', '));
          setFee(data.fee != null ? data.fee : '');
          if (!code && data.collection_code) setThingCollectionCode(data.collection_code);
          if (data.collection_headline) setThingCollectionHeadline(data.collection_headline);
        } else {
          setToast({ type: 'error', message: 'Error loading thing.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Connection error.' });
      } finally {
        setLoading(false);
      }
    };
    fetchThing();
  }, [token, thingCode, navigate]);

  const returnPath = thingCollectionCode ? `/collections/${thingCollectionCode}` : '/';
  const returnLabel = thingCollectionHeadline || (thingCollectionCode ? 'Collection' : 'Home');

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'Title is required.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    if (FEE_TYPES.includes(thingType) && (fee === '' || fee === undefined)) {
      newErrors.fee = 'Price is required for this type.';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = { type: thingType, headline: headline.trim() };
    body.description = description.trim() || '';
    body.thumbnail = thumbnail.trim() || '';
    if (pictures.trim()) {
      body.pictures = pictures.split(',').map((s) => s.trim()).filter(Boolean);
    } else {
      body.pictures = [];
    }
    if (FEE_TYPES.includes(thingType) && fee !== '') {
      body.fee = fee;
    }

    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(returnPath);
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

  const handleDelete = async () => {
    setDeleting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/`, {
        method: 'DELETE',
      });
      if (res.ok || res.status === 204) {
        navigate(returnPath);
      } else {
        setToast({ type: 'error', message: 'Error deleting thing.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return <div className="page-container"><p>Loading...</p></div>;
  }

  const steps = [
    {
      title: 'Type',
      description: (
        <Select
          options={TYPE_OPTIONS}
          value={thingType}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setThingType(selectedOptions[0].value);
            }
          }}
        />
      ),
    },
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
            label="Photos (comma-separated IDs)"
            value={pictures}
            onChange={(e) => setPictures(e.target.value)}
          />
          {FEE_TYPES.includes(thingType) && (
            <NumberInput
              label="Price"
              value={fee === '' ? '' : Number(fee)}
              onChange={(e) => setFee(e.target.value)}
              min={0}
              step={0.01}
              unit="EUR"
              required
              invalid={!!errors.fee}
              errorText={errors.fee}
            />
          )}
        </div>
      ),
    },
    {
      title: 'Summary',
      description: (
        <div>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Type</strong></dt>
            <dd>{TYPE_LABELS[thingType] || thingType}</dd>
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
            {pictures && (
              <>
                <dt><strong>Photos</strong></dt>
                <dd>{pictures}</dd>
              </>
            )}
            {FEE_TYPES.includes(thingType) && fee !== '' && (
              <>
                <dt><strong>Price</strong></dt>
                <dd>{fee} EUR</dd>
              </>
            )}
          </dl>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <Button disabled={submitting || deleting} onClick={handleSubmit}>
              {submitting ? 'Saving...' : 'Save'}
            </Button>
            <Button variant="danger" disabled={submitting || deleting} onClick={handleDelete}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <BackLink to={returnPath} label={returnLabel} />
      <StepByStep title="Edit thing" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
