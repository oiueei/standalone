import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Select,
  StepByStep,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Notification,
} from 'hds-react';

const TYPE_OPTIONS = [
  { label: 'Regalo', value: 'GIFT_THING' },
  { label: 'Venta', value: 'SELL_THING' },
  { label: 'Pedido', value: 'ORDER_THING' },
  { label: 'Alquiler', value: 'RENT_THING' },
  { label: 'Prestamo', value: 'LEND_THING' },
  { label: 'Compartir', value: 'SHARE_THING' },
];

const FEE_TYPES = ['SELL_THING', 'RENT_THING', 'ORDER_THING'];

const TYPE_LABELS = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]));

export default function AddThingPage() {
  const { code } = useParams();
  const navigate = useNavigate();

  const token = localStorage.getItem('token');
  if (!token) {
    navigate('/login');
  }

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
    fetch(`/api/v1/collections/${code}/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setCollectionHeadline(data.headline || ''))
      .catch(() => {});
  }, [token, code]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'El titulo es obligatorio.';
    if (headline.length > 64) newErrors.headline = 'Maximo 64 caracteres.';
    if (thumbnail.length > 16) newErrors.thumbnail = 'Maximo 16 caracteres.';
    if (FEE_TYPES.includes(type) && (fee === '' || fee === undefined)) {
      newErrors.fee = 'El precio es obligatorio para este tipo.';
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
      const res = await fetch('/api/v1/things/', {
        method: 'POST',
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
        const message = data.detail || Object.values(data).flat().join(' ') || 'Error al crear la cosa.';
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
      title: 'Tipo',
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
            invalid={!!errors.thumbnail}
            errorText={errors.thumbnail}
          />
          <TextInput
            label="Fotos (IDs separados por comas)"
            value={pictures}
            onChange={(e) => setPictures(e.target.value)}
          />
          {FEE_TYPES.includes(type) && (
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
            <dd>{TYPE_LABELS[type]}</dd>
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
            {FEE_TYPES.includes(type) && fee !== '' && (
              <>
                <dt><strong>Precio</strong></dt>
                <dd>{fee} EUR</dd>
              </>
            )}
          </dl>
          <div style={{ marginTop: '1rem' }}>
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
      <Link to={`/collections/${code}`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {collectionHeadline || 'Colección'}
      </Link>
      <StepByStep title="Anadir cosa" steps={steps} numberedList />

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
