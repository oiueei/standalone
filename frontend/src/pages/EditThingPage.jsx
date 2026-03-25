import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Select,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Dialog,
  Koros,
} from 'hds-react';
import { TYPE_OPTIONS, TYPE_LABELS, FEE_TYPES, DETAIL_TYPES, AVAILABILITY_OPTIONS, AVAILABILITY_LABELS, CONDITION_OPTIONS, CONDITION_LABELS } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function EditThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  const [loading, setLoading] = useState(true);
  const [thingType, setThingType] = useState('');
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
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [toast, setToast] = useState(null);
  const [thingCollectionCode, setThingCollectionCode] = useState(code || '');
  const [thingCollectionHeadline, setThingCollectionHeadline] = useState('');

  useEffect(() => {
    if (!userCode) {
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
          setAvailability(data.availability || '');
          setLocation(data.location || '');
          setCondition(data.condition || '');
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
  }, [userCode, thingCode, navigate]);

  const returnPath = thingCollectionCode ? `/collections/${thingCollectionCode}` : '/';
  const returnLabel = thingCollectionHeadline || (thingCollectionCode ? 'Collection' : 'Home');

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'Title is required.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    if (FEE_TYPES.includes(thingType) && (fee === '' || fee === undefined)) {
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
    if (DETAIL_TYPES.includes(thingType)) {
      body.availability = availability || '';
      body.location = location.trim();
      body.condition = condition || '';
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
    return <LoadingSpinner />;
  }

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
          <BackLink to={returnPath} label={returnLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">Edit thing</h1>
      <div className="form-grid">
        <Select
          id="edit-thing-type"
          texts={{ label: 'Type' }}
          options={TYPE_OPTIONS}
          value={thingType}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setThingType(selectedOptions[0].value);
            }
          }}
        />
        <TextInput
          id="edit-thing-headline"
          label="Title"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={`${headline.length}/64`}
        />
        <TextArea
          id="edit-thing-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <TextInput
          id="edit-thing-pictures"
          label="Photos (comma-separated IDs)"
          value={pictures}
          onChange={(e) => setPictures(e.target.value)}
        />
        {FEE_TYPES.includes(thingType) && (
          <NumberInput
            id="edit-thing-fee"
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
        {DETAIL_TYPES.includes(thingType) && (
          <>
            <Select
              id="edit-thing-availability"
              texts={{ label: 'Availability' }}
              options={AVAILABILITY_OPTIONS}
              value={availability}
              onChange={(sel) => sel.length > 0 && setAvailability(sel[0].value)}
              clearable
            />
            <TextInput
              id="edit-thing-location"
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              helperText={`${location.length}/32`}
              invalid={!!errors.location}
              errorText={errors.location}
            />
            <Select
              id="edit-thing-condition"
              texts={{ label: 'Condition' }}
              options={CONDITION_OPTIONS}
              value={condition}
              onChange={(sel) => sel.length > 0 && setCondition(sel[0].value)}
              clearable
            />
          </>
        )}
      </div>
      <div className="form-actions">
        <Button fullWidth disabled={submitting || deleting} onClick={handleSubmit} style={btnStyle}>
          {submitting ? 'Saving...' : 'Save'}
        </Button>
        <Button variant="secondary" fullWidth disabled={submitting || deleting} onClick={() => setConfirmDelete(true)} style={{
          '--border-color': 'var(--color-error)',
          '--color': 'var(--color-error)',
          '--background-color-hover': 'var(--color-error)',
          '--color-hover': 'var(--color-white)',
          marginTop: 'var(--spacing-s)',
        }}>
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
      <Dialog
        id="confirm-delete-thing"
        aria-labelledby="confirm-delete-thing-header"
        isOpen={confirmDelete}
        close={() => setConfirmDelete(false)}
        closeButtonLabelText="Cancel"
        theme={{ '--accent-line-color': 'var(--color-error)' }}
      >
        <Dialog.Header id="confirm-delete-thing-header" title="Delete thing?" />
        <Dialog.Content>
          <p>This action cannot be undone. Are you sure you want to delete this thing?</p>
        </Dialog.Content>
        <Dialog.ActionButtons>
          <Button variant="danger" onClick={() => { setConfirmDelete(false); handleDelete(); }}>
            Delete
          </Button>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
            Cancel
          </Button>
        </Dialog.ActionButtons>
      </Dialog>
      </div>
    </div>
  );
}
