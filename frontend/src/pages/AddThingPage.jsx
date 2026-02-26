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

export default function AddThingPage() {
  const { code } = useParams();
  const navigate = useNavigate();

  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [type, setType] = useState('GIFT_THING');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [pictures, setPictures] = useState('');
  const [fee, setFee] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!token) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setCollectionHeadline(data.headline || ''))
      .catch(() => {});
  }, [token, code]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'Title is required.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    if (thumbnail.length > 16) newErrors.thumbnail = 'Maximum 16 characters.';
    if (FEE_TYPES.includes(type) && (fee === '' || fee === undefined)) {
      newErrors.fee = 'Price is required for this type.';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      type,
      headline: headline.trim(),
      collection_code: code,
    };
    if (thumbnail.trim()) body.thumbnail = thumbnail.trim();
    if (description.trim()) body.description = description.trim();
    if (pictures.trim()) {
      body.pictures = pictures.split(',').map((s) => s.trim()).filter(Boolean);
    }
    if (FEE_TYPES.includes(type) && fee !== '') {
      body.fee = fee;
    }

    try {
      const res = await apiFetch('/api/v1/things/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
      } else {
        const data = await res.json().catch(() => ({}));
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error creating thing.';
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
      title: 'Type',
      description: (
        <Select
          options={TYPE_OPTIONS}
          value={type}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setType(selectedOptions[0].value);
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
            invalid={!!errors.thumbnail}
            errorText={errors.thumbnail}
          />
          <TextInput
            label="Photos (comma-separated IDs)"
            value={pictures}
            onChange={(e) => setPictures(e.target.value)}
          />
          {FEE_TYPES.includes(type) && (
            <NumberInput
              label="Price"
              value={fee === '' ? '' : Number(fee)}
              onChange={(e) => setFee(e.target.value)}
              min={0}
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
            <dd>{TYPE_LABELS[type]}</dd>
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
            {FEE_TYPES.includes(type) && fee !== '' && (
              <>
                <dt><strong>Price</strong></dt>
                <dd>{fee} EUR</dd>
              </>
            )}
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
      <BackLink to={`/collections/${code}`} label={collectionHeadline || 'Collection'} />
      <StepByStep title="Add thing" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
