import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Button, Notification } from 'hds-react';

export default function EditProfilePage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const [loading, setLoading] = useState(true);
  const [userCode, setUserCode] = useState('');
  const [name, setName] = useState('');
  const [headline, setHeadline] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [hero, setHero] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/v1/auth/me/', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUserCode(data.code);
          setName(data.name || '');
          setHeadline(data.headline || '');
          setThumbnail(data.thumbnail || '');
          setHero(data.hero || '');
        } else {
          setToast({ type: 'error', message: 'Error al cargar el perfil.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Error de conexion.' });
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [token, navigate]);

  const validate = () => {
    const newErrors = {};
    if (name.length > 32) newErrors.name = 'Maximo 32 caracteres.';
    if (headline.length > 64) newErrors.headline = 'Maximo 64 caracteres.';
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
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error al guardar.';
        setToast({ type: 'error', message });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion con el servidor.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  const steps = [
    {
      title: 'Detalles',
      description: (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Nombre"
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
        </div>
      ),
    },
    {
      title: 'Resumen',
      description: (
        <div>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Nombre</strong></dt>
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
          </dl>
          <div style={{ marginTop: '1rem' }}>
            <Button disabled={submitting} onClick={handleSubmit}>
              {submitting ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <Link to="/" style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; Home
      </Link>
      <StepByStep title="Editar perfil" steps={steps} numberedList />

      {toast && (
        <Notification
          label={toast.type === 'success' ? 'Listo' : 'Error'}
          type={toast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Cerrar"
          onClose={() => setToast(null)}
        >
          {toast.message}
        </Notification>
      )}
    </div>
  );
}
