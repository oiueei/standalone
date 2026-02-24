import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { StepByStep, TextInput, TextArea, Select, Button, Notification } from 'hds-react';

const STATUS_OPTIONS = [
  { label: 'Activa', value: 'ACTIVE' },
  { label: 'Inactiva', value: 'INACTIVE' },
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
        const [collectionRes, theemesRes] = await Promise.all([
          fetch(`/api/v1/collections/${code}/`, {
            headers: { 'Authorization': `Bearer ${token}` },
          }),
          fetch('/api/v1/theeemes/', {
            headers: { 'Authorization': `Bearer ${token}` },
          }),
        ]);

        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setHero(data.hero || '');
          setStatus(data.status || 'ACTIVE');
          setTheeeme(data.theeeme || '');
        } else {
          setToast({ type: 'error', message: 'Error al cargar la coleccion.' });
        }

        if (theemesRes.ok) {
          const data = await theemesRes.json();
          setTheeemes(Array.isArray(data) ? data : data.results || []);
        }
      } catch {
        setToast({ type: 'error', message: 'Error de conexion.' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token, code, navigate]);

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

    const body = {
      headline: headline.trim(),
      description: description.trim(),
      thumbnail: thumbnail.trim(),
      hero: hero.trim(),
      status,
    };
    if (theeeme) body.theeeme = theeeme;

    try {
      const res = await fetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
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

  const theeemeOptions = theeemes.map((t) => ({ label: t.name, value: t.code }));
  const selectedTheemeName = theeemes.find((t) => t.code === theeeme)?.name || theeeme || '—';

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
          <Select
            label="Estado"
            options={STATUS_OPTIONS}
            value={status}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                setStatus(selectedOptions[0].value);
              }
            }}
          />
          {theeemeOptions.length > 0 && (
            <Select
              label="Tema"
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
            <dt><strong>Estado</strong></dt>
            <dd>{status === 'ACTIVE' ? 'Activa' : 'Inactiva'}</dd>
            <dt><strong>Tema</strong></dt>
            <dd>{selectedTheemeName}</dd>
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
      <Link to={`/collections/${code}`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {headline || 'Colección'}
      </Link>
      <StepByStep title="Editar coleccion" steps={steps} numberedList />

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
