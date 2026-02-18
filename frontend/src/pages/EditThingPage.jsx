import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Select,
  StepByStep,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Notification,
} from 'oiueeiDS-react';

const FEE_TYPES = ['SELL_THING', 'RENT_THING', 'ORDER_THING'];

const TYPE_OPTIONS = [
  { label: 'Regalo', value: 'GIFT_THING' },
  { label: 'Venta', value: 'SELL_THING' },
  { label: 'Pedido', value: 'ORDER_THING' },
  { label: 'Alquiler', value: 'RENT_THING' },
  { label: 'Prestamo', value: 'LEND_THING' },
  { label: 'Compartir', value: 'SHARE_THING' },
];

const TYPE_LABELS = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]));

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

  const returnPath = code ? `/collections/${code}` : '/';

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    const fetchThing = async () => {
      try {
        const res = await fetch(`/api/v1/things/${thingCode}/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setThingType(data.type);
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setPictures((data.pictures || []).join(', '));
          setFee(data.fee != null ? data.fee : '');
        } else {
          setToast({ type: 'error', message: 'Error al cargar la cosa.' });
        }
      } catch {
        setToast({ type: 'error', message: 'Error de conexion.' });
      } finally {
        setLoading(false);
      }
    };
    fetchThing();
  }, [token, thingCode, navigate]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'El titulo es obligatorio.';
    if (headline.length > 64) newErrors.headline = 'Maximo 64 caracteres.';
    if (FEE_TYPES.includes(thingType) && (fee === '' || fee === undefined)) {
      newErrors.fee = 'El precio es obligatorio para este tipo.';
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
      const res = await fetch(`/api/v1/things/${thingCode}/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(returnPath);
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

  const handleDelete = async () => {
    setDeleting(true);
    setToast(null);
    try {
      const res = await fetch(`/api/v1/things/${thingCode}/`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok || res.status === 204) {
        navigate(returnPath);
      } else {
        setToast({ type: 'error', message: 'Error al eliminar la cosa.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  const steps = [
    {
      title: 'Tipo',
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
            label="Fotos (IDs separados por comas)"
            value={pictures}
            onChange={(e) => setPictures(e.target.value)}
          />
          {FEE_TYPES.includes(thingType) && (
            <NumberInput
              label="Precio"
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
      title: 'Resumen',
      description: (
        <div>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Tipo</strong></dt>
            <dd>{TYPE_LABELS[thingType] || thingType}</dd>
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
            {pictures && (
              <>
                <dt><strong>Fotos</strong></dt>
                <dd>{pictures}</dd>
              </>
            )}
            {FEE_TYPES.includes(thingType) && fee !== '' && (
              <>
                <dt><strong>Precio</strong></dt>
                <dd>{fee} EUR</dd>
              </>
            )}
          </dl>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <Button variant="secondary" onClick={() => navigate(returnPath)}>Cancelar</Button>
            <Button disabled={submitting || deleting} onClick={handleSubmit}>
              {submitting ? 'Guardando...' : 'Guardar'}
            </Button>
            <Button variant="danger" disabled={submitting || deleting} onClick={handleDelete}>
              {deleting ? 'Eliminando...' : 'Eliminar'}
            </Button>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container">
      <StepByStep title="Editar cosa" steps={steps} numberedList />

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
