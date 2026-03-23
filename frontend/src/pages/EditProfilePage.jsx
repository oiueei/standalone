import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Select, Button } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function EditProfilePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Home';
  const userCode = localStorage.getItem('userCode');

  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [headline, setHeadline] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [hero, setHero] = useState('');
  const [theeeme, setTheeeme] = useState('');
  const [theeemes, setTheeemes] = useState([]);
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
        const [profileRes, theemesRes] = await Promise.all([
          apiFetch('/api/v1/auth/me/'),
          apiFetch('/api/v1/theeemes/'),
        ]);

        if (profileRes.ok) {
          const data = await profileRes.json();
          setName(data.name || '');
          setHeadline(data.headline || '');
          setThumbnail(data.thumbnail || '');
          setHero(data.hero || '');
          setTheeeme(data.theeeme || '');
        } else {
          setToast({ type: 'error', message: 'Error loading profile.' });
        }

        if (theemesRes.ok) {
          const data = await theemesRes.json();
          setTheeemes(Array.isArray(data) ? data : data.results || []);
        }
      } catch {
        setToast({ type: 'error', message: 'Connection error.' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [userCode, navigate]);

  const validate = () => {
    const newErrors = {};
    if (name.length > 32) newErrors.name = 'Maximum 32 characters.';
    if (headline.length > 64) newErrors.headline = 'Maximum 64 characters.';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      name: name.trim(),
      headline: headline.trim(),
      thumbnail: thumbnail.trim(),
      hero: hero.trim(),
    };
    if (theeeme) body.theeeme = theeeme;

    try {
      const res = await apiFetch(`/api/v1/users/${userCode}/`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate('/');
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

  const theeemeOptions = theeemes.map((t) => ({ label: t.name, value: t.code }));
  const selectedTheemeName = theeemes.find((t) => t.code === theeeme)?.name || theeeme || '—';

  const steps = [
    {
      title: 'Details',
      description: (
        <div className="form-grid">
          <TextInput
            id="edit-profile-name"
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            invalid={!!errors.name}
            errorText={errors.name}
            helperText={`${name.length}/32`}
          />
          <TextArea
            id="edit-profile-headline"
            label="Bio"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextInput
            id="edit-profile-thumbnail"
            label="Thumbnail (Cloudinary ID)"
            value={thumbnail}
            onChange={(e) => setThumbnail(e.target.value)}
          />
          <TextInput
            id="edit-profile-hero"
            label="Hero (Cloudinary ID)"
            value={hero}
            onChange={(e) => setHero(e.target.value)}
          />
          {theeemeOptions.length > 0 && (
            <Select
              id="edit-profile-theeeme"
              texts={{ label: 'Theeeme' }}
              options={theeemeOptions}
              value={theeeme}
              onChange={(selectedOptions) => {
                if (selectedOptions.length > 0) {
                  setTheeeme(selectedOptions[0].value);
                }
              }}
            />
          )}
        </div>
      ),
    },
    {
      title: 'Summary',
      description: (
        <div>
          <dl className="summary-grid">
            <dt><strong>Name</strong></dt>
            <dd>{name || '—'}</dd>
            {headline && (
              <>
                <dt><strong>Bio</strong></dt>
                <dd>{headline}</dd>
              </>
            )}
            <dt><strong>Thumbnail</strong></dt>
            <dd>{thumbnail || '—'}</dd>
            <dt><strong>Hero</strong></dt>
            <dd>{hero || '—'}</dd>
            <dt><strong>Theeeme</strong></dt>
            <dd>{selectedTheemeName}</dd>
          </dl>
          <div className="section-mt">
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
      <BackLink to={backPath} label={backLabel} />
      <StepByStep title="Edit profile" steps={steps} numberedList />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
