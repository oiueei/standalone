import { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Select, Button, Notification } from 'hds-react';

export default function EditProfilePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Home';
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [userCode, setUserCode] = useState('');
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
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const [profileRes, theemesRes] = await Promise.all([
          fetch('/api/v1/auth/me/', {
            headers: { 'Authorization': `Bearer ${token}` },
          }),
          fetch('/api/v1/theeemes/', {
            headers: { 'Authorization': `Bearer ${token}` },
          }),
        ]);

        if (profileRes.ok) {
          const data = await profileRes.json();
          setUserCode(data.code);
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
  }, [token, navigate]);

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
      const res = await fetch(`/api/v1/users/${userCode}/`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
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
    return <div className="page-container"><p>Loading...</p></div>;
  }

  const theeemeOptions = theeemes.map((t) => ({ label: t.name, value: t.code }));
  const selectedTheemeName = theeemes.find((t) => t.code === theeeme)?.name || theeeme || '—';

  const steps = [
    {
      title: 'Details',
      description: (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            invalid={!!errors.name}
            errorText={errors.name}
          />
          <TextArea
            label="Bio"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            invalid={!!errors.headline}
            errorText={errors.headline}
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
          {theeemeOptions.length > 0 && (
            <Select
              label="Theeeme"
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
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
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
      <Link to={backPath} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {backLabel}
      </Link>
      <StepByStep title="Edit profile" steps={steps} numberedList />

      {toast && (
        <Notification
          label={toast.type === 'success' ? 'Done' : 'Error'}
          type={toast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Close"
          onClose={() => setToast(null)}
        >
          {toast.message}
        </Notification>
      )}
    </div>
  );
}
