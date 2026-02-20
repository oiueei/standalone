import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Button, Notification } from 'hds-react';

export default function CreateCollectionPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  if (!token) {
    navigate('/login');
  }

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [hero, setHero] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'El titulo es obligatorio.';
    if (headline.length > 64) newErrors.headline = 'Maximo 64 caracteres.';
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
      const res = await fetch('/api/v1/collections/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        navigate(`/collections/${data.code}`);
      } else {
        const data = await res.json().catch(() => ({}));
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error al crear la coleccion.';
        setToast({ type: 'error', message });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion con el servidor.' });
    } finally {
      setSubmitting(false);
    }
  };

  const steps = [
    {
      title: 'Detalles',
      description: (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <TextInput
            label="Titulo"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            required
            invalid={!!errors.headline}
            errorText={errors.headline}
          />
          <TextArea
            label="Descripcion"
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
      title: 'Resumen',
      description: (
        <div>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Titulo</strong></dt>
            <dd>{headline || '—'}</dd>
            {description && (
              <>
                <dt><strong>Descripcion</strong></dt>
                <dd>{description}</dd>
              </>
            )}
            <dt><strong>Thumbnail</strong></dt>
            <dd>{thumbnail || '—'}</dd>
            <dt><strong>Hero</strong></dt>
            <dd>{hero || '—'}</dd>
          </dl>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <Button variant="secondary" onClick={() => navigate('/')}>Cancelar</Button>
            <Button disabled={submitting} onClick={handleSubmit}>
              {submitting ? 'Creando...' : 'Crear'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <StepByStep title="Crear coleccion" steps={steps} numberedList />

      {toast && (
        <Notification
          label="Error"
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
