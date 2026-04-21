# Plan de seeds F01–F15

> **Estado**: Borrador. Revisar y rellenar antes de ejecutar.  
> **Objetivo**: Que cualquier persona que clone el repo pueda testear manualmente todas las features F01–F15 sin crear datos de cero.  
> **Estrategia**: Una migración de datos por bloque temático. Seguras con `get_or_create`. Las fotos y documentos se suben a Cloudinary manualmente y se conectan vía `public_id` en la migración.

---

## Nuevas personas

Cuatro nuevos usuarios con personalidades claras para escenarios de prueba:

| Código sugerido | Email | Nombre | Rol en los tests |
|-----------------|-------|--------|-----------------|
| `lel0xy` | lelo@mail.com | **Lelo** | Músico. Da clases de guitarra (APPOINTMENT_THING). Tiene cosas raras para intercambiar. |
| `l0laxy` | lola@mail.com | **Lola** | Mercadillo. Tiene una colección SWAP pura: solo intercambios, sin dinero. |
| `lulazy` | lula@mail.com | **Lula** | Vecina activa. Comparte una furgoneta con Lili (ASSET_THING por horas). Manda S.O.S. |
| `lil0xy` | lilo@mail.com | **Lilo** | Organizador de eventos. Crea EVENT_THING y gestiona la newsletter SHARE. |

> Los códigos son sugerencias. Usar `secrets.choice(string.ascii_letters + string.digits)` para generar los definitivos antes de commitear.

---

## Migración 0064 — Nuevos usuarios

```python
# core/migrations/0064_seed_new_users_lelo_lola_lula_lilo.py

USERS = [
    {
        "code": "lel0xy",  # ← reemplazar con código generado
        "email": "lelo@mail.com",
        "name": "Lelo",
        "headline": "Guitar teacher, swap enthusiast, neighbour extraordinaire!",
        "koro": "beat",
    },
    {
        "code": "l0laxy",  # ← reemplazar
        "email": "lola@mail.com",
        "name": "Lola",
        "headline": "Swap queen – no money, just good vibes and fair trades!",
        "koro": "wave",
    },
    {
        "code": "lulazy",  # ← reemplazar
        "email": "lula@mail.com",
        "name": "Lula",
        "headline": "Shares the van, shares the love – S.O.S. queen!",
        "koro": "calm",
    },
    {
        "code": "lil0xy",  # ← reemplazar
        "email": "lilo@mail.com",
        "name": "Lilo",
        "headline": "Event organiser, newsletter curator, always in the loop!",
        "koro": "pulse",
    },
]
```

**Dependencias**: `0063_add_is_minimalist_to_collection`

---

## Migración 0065 — Colecciones nuevas

### A. Colección de Lelo: Guitar Studio (PROPRIETARY, con APPOINTMENT_THING)
```python
{
    "code": "lel0C1",  # ← reemplazar
    "owner": "lelo",
    "headline": "Lelo's Guitar Studio – Book a lesson!",
    "description": "One-to-one guitar lessons for all levels. **Classical, folk, and fingerpicking.**\n\n- Beginners welcome\n- Bring your own guitar or borrow mine\n- Sessions in the common room",
    "mode": "PROPRIETARY",
}
# Invitados: Lula, Lilo (y Lala de los seeds anteriores)
```

### B. Colección de Lola: El Mercadillo (COMMUNITY + is_swap=True)
```python
{
    "code": "l0laC1",  # ← reemplazar
    "owner": "lola",
    "headline": "Lola's Mercadillo – swaps only, no cash!",
    "description": "Pure exchange economy. Offer something, get something. **No prices, no euros, just trust.**\n\n- Only swap proposals accepted\n- Be fair, be kind\n- Weekly roundup every Monday",
    "mode": "COMMUNITY",
    "is_swap": True,
    "digest_frequency": "WEEKLY",
}
# Invitados: Lelo, Lula, Lilo, Lali (seed anterior)
```

### C. Colección de Lila + Lilo: La Furgoneta (COMMUNITY + is_share=True + newsletter)
> Lila y Lilo comparten la furgoneta de Lili (Lili es dueña de la colección; Lilo y Lula son invitadas con permiso de añadir things en modo COMMUNITY).

```python
{
    "code": "lilCv1",  # ← reemplazar
    "owner": "lili",   # ← Lili de los seeds anteriores
    "headline": "The Van Pool – shared wheels for the neighbourhood",
    "description": "Our community van. Book it by the hour for moving stuff, airport runs, or weekend trips. **Check the calendar before booking.**",
    "mode": "COMMUNITY",
    "is_share": False,   # ← La furgoneta es ASSET, no SHARE. Ver nota abajo.
    "newsletter_enabled": False,
}
# Nota: ASSET_THING no requiere is_share. is_share es solo para SHARE_THING.
# Invitados: Lula, Lilo, Lola, Lala
```

### D. Colección de Lilo: Share & Newsletter (COMMUNITY + is_share + newsletter)
```python
{
    "code": "lil0C2",  # ← reemplazar
    "owner": "lilo",
    "headline": "Lilo's Free Stuff Circle – share the love!",
    "description": "Things looking for a new home. Pass them on, keep them alive. Weekly newsletter every Monday with what moved and what's new.",
    "mode": "COMMUNITY",
    "is_share": True,
    "newsletter_enabled": True,
}
# Invitados: todos los usuarios del sistema
```

### E. Colección de Lola: Álbum minimalista (is_minimalist=True)
```python
{
    "code": "l0laC2",  # ← reemplazar
    "owner": "lola",
    "headline": "Lola's Photo Shelf – spot something you want?",
    "description": "A clean album of things to swap or gift. One photo, one caption. That's all.",
    "mode": "COMMUNITY",
    "is_minimalist": True,
}
# Invitados: Lelo, Lula, Lilo
```

**Dependencias**: `0064_seed_new_users_...`

---

## Migración 0066 — Things nuevas

### Lelo → Guitar Studio (APPOINTMENT_THING)
```python
{
    "code": "lel0t1",  # ← reemplazar
    "collection": "lel0C1",
    "type": "APPOINTMENT_THING",
    "owner": "lelo",
    "headline": "Guitar Lesson – 1h with Lelo",
    "description": "All levels welcome. Classical, folk, fingerpicking. Book your slot!",
    "slot_duration": 60,
    "availability_schedule": [
        {"days": [1, 3, 5], "start_time": "10:00", "end_time": "14:00"}
    ],  # Lunes, miércoles, viernes, 10-14h
    "status": "ACTIVE",
}
```

### Lila → La Furgoneta (ASSET_THING por horas)
```python
{
    "code": "liltv1",  # ← reemplazar
    "collection": "lilCv1",
    "type": "ASSET_THING",
    "owner": "lili",
    "headline": "Community Van – Citroën Berlingo",
    "description": "Seats 5 + boot space. Perfect for IKEA runs, airport pickups, or moving boxes. **Book by the hour.** Return with a full tank.",
    "booking_unit": "HOUR",
    "status": "ACTIVE",
    # thumbnail: subir foto a Cloudinary y poner public_id aquí
    # "thumbnail": "oiueei/van_001",
}
```

### Lola → El Mercadillo (SWAP_THING × 3)
```python
# Lola ofrece:
{
    "code": "l0lat1",
    "collection": "l0laC1",
    "type": "SWAP_THING",
    "owner": "lola",
    "headline": "Vintage denim jacket – size M",
    "description": "90s Levi's trucker jacket. Barely worn. Looking for books or plants.",
    "condition": "GOOD",
    "status": "ACTIVE",
},
{
    "code": "l0lat2",
    "collection": "l0laC1",
    "type": "SWAP_THING",
    "owner": "lola",
    "headline": "Pasta machine Imperia 150",
    "description": "Manual, 7 settings, full set. Swapping for kitchen things or tools.",
    "condition": "GOOD",
    "status": "ACTIVE",
},
# Lelo también añade cosas al mercadillo (COMMUNITY):
{
    "code": "lel0t2",
    "collection": "l0laC1",
    "type": "SWAP_THING",
    "owner": "lelo",
    "headline": "Guitar capo – Kyser Quick-Change",
    "description": "Capo for acoustic guitar. All keys. Swapping for anything musical.",
    "condition": "NEW",
    "status": "ACTIVE",
},
```

### Lilo → Free Stuff Circle (SHARE_THING × 3)
```python
{
    "code": "lil0t1",
    "collection": "lil0C2",
    "type": "SHARE_THING",
    "owner": "lilo",
    "headline": "Standing Desk Converter",
    "description": "Adjustable height converter. Fits most desks. Pass it on when you're done!",
    "condition": "GOOD",
    "status": "ACTIVE",
},
{
    "code": "lil0t2",
    "collection": "lil0C2",
    "type": "SHARE_THING",
    "owner": "lilo",
    "headline": "Bread maker – Moulinex OW240E",
    "description": "12 programs, barely used. The neighbourhood should taste fresh bread.",
    "condition": "GOOD",
    "status": "ACTIVE",
},
{
    "code": "lil0t3",
    "collection": "lil0C2",
    "type": "SHARE_THING",
    "owner": "lilo",
    "headline": "Yoga mat – 6mm foam",
    "description": "Purple, non-slip. Pass to whoever needs it most.",
    "condition": "USED",
    "status": "ACTIVE",
},
```

### Lula → S.O.S. (WISH_THING × 2 en colección COMMUNITY de Lulu)
> Lula es invitada a la colección de Lulu (Phantom Shelf, COMMUNITY). Añade sus wishes.

```python
{
    "code": "lulat1",
    "collection": "1u1uC1",  # Phantom Shelf de Lulu (seed anterior)
    "type": "WISH_THING",
    "owner": "lula",
    "headline": "S.O.S. – anyone have a cargo bike I can borrow?",
    "description": "Need it for one weekend to move a mattress. Happy to return clean and with a thank-you cake!",
    "status": "ACTIVE",
},
{
    "code": "lulat2",
    "collection": "1u1uC1",
    "type": "WISH_THING",
    "owner": "lula",
    "headline": "S.O.S. – looking for a printer for one page",
    "description": "Need to print one document urgently. Any neighbour with a printer?",
    "status": "ACTIVE",
},
```

### Lilo → Evento en el club de libros de Lolo (EVENT_THING)
> Lilo está invitado a la colección de Lolo. Añade un evento de lectura.

```python
{
    "code": "lil0ev",
    "collection": "l0l0C1",  # Book club de Lolo (seed anterior)
    "type": "EVENT_THING",
    "owner": "lilo",
    "headline": "Book Club session – Tess of the D'Urbervilles",
    "description": "**Sunday 3 May, 11:00h** — Common room, 2nd floor.\n\nBring the book (borrowed from Lolo!) and your feelings about Angel Clare. Tea provided.",
    "event_date": "2026-05-03T11:00:00+02:00",
    "status": "ACTIVE",
},
```

### Lola → Álbum minimalista (GIFT_THING × 2 con fotos)
```python
{
    "code": "l0lam1",
    "collection": "l0laC2",
    "type": "GIFT_THING",
    "owner": "lola",
    "headline": "Terrarium with air plants",
    "condition": "GOOD",
    "status": "ACTIVE",
    # thumbnail: "oiueei/terrarium_001" ← subir a Cloudinary primero
},
{
    "code": "l0lam2",
    "collection": "l0laC2",
    "type": "GIFT_THING",
    "owner": "lola",
    "headline": "Wicker basket – market size",
    "condition": "USED",
    "status": "ACTIVE",
    # thumbnail: "oiueei/basket_001" ← subir a Cloudinary primero
},
```

**Dependencias**: `0065_seed_new_collections_...`

---

## Migración 0067 — ThingTransfer de ejemplo (Cadena de Lilo)

Para demostrar la cadena de transferencias sin tener que hacer booking manual:

```python
# Lilo → Lula → Lolo para el "Standing Desk Converter"
# lent_date debe ser en el pasado
ThingTransfer(
    thing="lil0t1",  # Standing Desk Converter
    from_user="lilo",
    to_user="lula",
    lent_date=date(2026, 3, 10),
    returned_date=date(2026, 3, 31),
)
ThingTransfer(
    thing="lil0t1",
    from_user="lula",
    to_user="lolo",
    lent_date=date(2026, 4, 1),
    returned_date=None,  # Lolo lo tiene ahora
)
# También actualizar thing.owner = lolo
```

> ⚠️ Para que esto sea coherente, también hay que cambiar `thing.owner` a `lolo`. En migration: `Thing.objects.filter(code="lil0t1").update(owner=lolo)`.

**Dependencias**: `0066_seed_new_things_...`

---

## Documentos adjuntos (F11)

Los documentos se guardan en Cloudinary con tipo `raw`. El flujo recomendado:

1. Sube el PDF/documento manualmente a Cloudinary en la carpeta `oiueei-docs/`.
2. Copia el `public_id` (ej. `oiueei-docs/rental_contract_001`).
3. En la migración, setea el campo `documents` del thing:

```python
Thing.objects.filter(code="liltv1").update(documents=[
    {
        "public_id": "oiueei-docs/van_rental_terms",
        "filename": "van_rental_terms.pdf",
        "content_type": "application/pdf",
    }
])
```

**Documento sugerido para la furgoneta**: un PDF simple de "Términos de uso de la furgoneta comunitaria" (1 página). Se envía automáticamente al aceptar una reserva.

---

## Script de reset para tests manuales

Al terminar los tests, necesitas volver al estado inicial de los seeds. Claude te preparará el script cuando termines los tests manuales, pero la estrategia será:

```bash
# Reset completo y re-aplicar todas las migraciones
python manage.py flush --no-input
python manage.py migrate
```

O, si quieres mantener los usuarios de auth:

```bash
# Borrar solo los datos de seeds nuevos (por código)
python manage.py shell -c "
from core.models import User, Collection, Thing, ThingTransfer
ThingTransfer.objects.filter(thing__code__in=['lil0t1']).delete()
Thing.objects.filter(code__startswith='lel0').delete()
# ... etc
"
```

> La estrategia definitiva (script bash con `manage.py`) se concretará cuando acabes los tests manuales. Pedírsela a Claude entonces.

---

## Checklist antes de hacer las migraciones

- [ ] Generar códigos de 6 caracteres reales para usuarios/colecciones/things (no usar los placeholders `lel0xy`, etc.)
- [ ] Verificar que los `headline` tienen ≤ 64 caracteres
- [ ] Verificar que los `description` tienen ≤ 256 caracteres  
- [ ] Verificar que los `name` tienen ≤ 32 caracteres
- [ ] Verificar que los `location` tienen ≤ 32 caracteres
- [ ] Subir fotos de furgoneta, terrarium y cesta a Cloudinary → anotar `public_id`
- [ ] Subir documento PDF de términos de furgoneta a Cloudinary → anotar `public_id`
- [ ] Conectar `thumbnail` y `documents` de los things correspondientes en la migración
- [ ] Revisar que `event_date` de la sesión del club de libros sigue siendo futura (ajustar si hace falta)
- [ ] Testar en local con `python manage.py migrate` antes de commitear
