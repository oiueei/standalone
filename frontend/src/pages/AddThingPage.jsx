import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Select,
  Stepper,
  StepState,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Notification,
} from 'oiueeiDS-react';

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

function getStepperSteps(currentStep) {
  const labels = ['Tipo', 'Detalles', 'Resumen'];
  return labels.map((label, i) => ({
    label,
    state:
      i < currentStep
        ? StepState.completed
        : i === currentStep
          ? StepState.available
          : StepState.disabled,
  }));
}

export default function AddThingPage() {
  const { code } = useParams();
  const navigate = useNavigate();

  const token = localStorage.getItem('token');
  if (!token) {
    navigate('/login');
  }

  const [step, setStep] = useState(0);
  const [type, setType] = useState('GIFT_THING');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [pictures, setPictures] = useState('');
  const [fee, setFee] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validateStep2 = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = 'El titulo es obligatorio.';
    if (headline.length > 64) newErrors.headline = 'Maximo 64 caracteres.';
    if (thumbnail.length > 16) newErrors.thumbnail = 'Maximo 16 caracteres.';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
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

  return (
    <div className="page-container">
      <h1 className="page-title">Anadir cosa</h1>
      <Stepper steps={getStepperSteps(step)} selectedStep={step} language="en" />

      {step === 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <Select
            options={TYPE_OPTIONS}
            value={type}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                setType(selectedOptions[0].value);
              }
            }}
          />
          <div style={{ marginTop: '1rem' }}>
            <Button onClick={() => setStep(1)}>Siguiente</Button>
          </div>
        </div>
      )}

      {step === 1 && (
        <div style={{ marginTop: '1.5rem', display: 'grid', gap: '1rem' }}>
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
            />
          )}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" onClick={() => setStep(0)}>Anterior</Button>
            <Button onClick={() => { if (validateStep2()) setStep(2); }}>Siguiente</Button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div style={{ marginTop: '1.5rem' }}>
          <dl style={{ display: 'grid', gap: '0.5rem' }}>
            <dt><strong>Tipo</strong></dt>
            <dd>{TYPE_LABELS[type]}</dd>
            <dt><strong>Titulo</strong></dt>
            <dd>{headline}</dd>
            {description && (
              <>
                <dt><strong>Descripcion</strong></dt>
                <dd>{description}</dd>
              </>
            )}
            <dt><strong>Thumbnail</strong></dt>
            <dd>{thumbnail}</dd>
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
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <Button variant="secondary" onClick={() => setStep(1)}>Anterior</Button>
            <Button disabled={submitting} onClick={handleSubmit}>
              {submitting ? 'Creando...' : 'Crear'}
            </Button>
          </div>
        </div>
      )}

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
