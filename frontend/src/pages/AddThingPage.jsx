import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Select,
  TextInput,
  TextArea,
  NumberInput,
  Button,
} from 'hds-react';
import { TYPE_OPTIONS, TYPE_LABELS, FEE_TYPES, DETAIL_TYPES, AVAILABILITY_OPTIONS, AVAILABILITY_LABELS, CONDITION_OPTIONS, CONDITION_LABELS } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function AddThingPage() {
  const { code } = useParams();
  const navigate = useNavigate();

  const userCode = localStorage.getItem('userCode');

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [type, setType] = useState('GIFT_THING');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [pictures, setPictures] = useState('');
  const [fee, setFee] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setCollectionHeadline(data.headline || ''))
      .catch(() => {});
  }, [userCode, code]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'Title is required.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    if (thumbnail.length > 16) newErrors.thumbnail = 'Maximum 16 characters.';
    if (FEE_TYPES.includes(type) && (fee === '' || fee === undefined)) {
      newErrors.fee = 'Price is required for this type.';
    }
    if (location.length > 32) newErrors.location = 'Maximum 32 characters.';
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
    if (DETAIL_TYPES.includes(type)) {
      if (availability) body.availability = availability;
      if (location.trim()) body.location = location.trim();
      if (condition) body.condition = condition;
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

  return (
    <div className="page-container">
      <BackLink to={`/collections/${code}`} label={collectionHeadline || 'Collection'} />

      <h1 className="page-title">Add thing</h1>
      <div className="form-grid">
          <Select
            id="add-thing-type"
            texts={{ label: 'Type' }}
            options={TYPE_OPTIONS}
            value={type}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                setType(selectedOptions[0].value);
              }
            }}
          />
          <TextInput
            id="add-thing-headline"
            label="Title"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            required
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextArea
            id="add-thing-description"
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <TextInput
            id="add-thing-pictures"
            label="Photos (comma-separated IDs)"
            value={pictures}
            onChange={(e) => setPictures(e.target.value)}
          />
          {FEE_TYPES.includes(type) && (
            <NumberInput
              id="add-thing-fee"
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
          {DETAIL_TYPES.includes(type) && (
            <>
              <Select
                id="add-thing-availability"
                texts={{ label: 'Availability' }}
                options={AVAILABILITY_OPTIONS}
                value={availability}
                onChange={(sel) => sel.length > 0 && setAvailability(sel[0].value)}
                clearable
              />
              <TextInput
                id="add-thing-location"
                label="Location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                helperText={`${location.length}/32`}
                invalid={!!errors.location}
                errorText={errors.location}
              />
              <Select
                id="add-thing-condition"
                texts={{ label: 'Condition' }}
                options={CONDITION_OPTIONS}
                value={condition}
                onChange={(sel) => sel.length > 0 && setCondition(sel[0].value)}
                clearable
              />
            </>
          )}
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
