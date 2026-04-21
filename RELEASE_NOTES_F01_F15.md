# OIUEEI — Release Notes F01–F15

> **Estado**: En tests manuales. Commits adicionales desde 2026-04-21.  
> **Rama**: `development`  
> **Fecha actualizada**: 2026-04-21

---

## Resumen ejecutivo

En esta tanda hemos construido el núcleo de la economía colaborativa de OIUEEI: once tipos de *thing*, cuatro modos de colección, y todas las piezas de comunicación que los sostienen. La arquitectura sigue siendo la misma (una sola app Django, vistas finas, servicios atómicos, serializers seguros), pero el modelo de dominio ha crecido enormemente.

---

## Tipos de colección

| Modo | Flags | Descripción |
|------|-------|-------------|
| **PROPRIETARY** | — | Colección privada. Solo el dueño añade things. |
| **COMMUNITY** | `mode=COMMUNITY` | Colección compartida. Los invitados pueden añadir sus propias things. |
| **COMMUNITY + Swap** | `is_swap=True` | Solo SWAP_THING. Intercambios bilaterales sin dinero. |
| **COMMUNITY + Share** | `is_share=True` | Solo SHARE_THING. Cadena de transferencias de propiedad. |
| **COMMUNITY + Share + Newsletter** | `newsletter_enabled=True` | Igual que Share + boletín semanal de actividad los lunes. |
| **Minimalist** | `is_minimalist=True` | Álbum de fotos. Solo GIFT/SHARE/SWAP. Thumbnail obligatorio. UI simplificada. |

> `is_swap` y `is_share` son mutuamente excluyentes. `is_minimalist` es compatible con `is_share`.

---

## Tipos de *thing*

### Things clásicos (sin cambios de arquitectura)

| Tipo | Descripción |
|------|-------------|
| `GIFT_THING` | Regalo. Sin fechas. Se desactiva al aceptar. |
| `SELL_THING` | Venta. Con precio. Se desactiva al aceptar. |
| `ORDER_THING` | Pedido recurrente. Con fecha de entrega y cantidad. Sigue activo. |
| `RENT_THING` | Alquiler. Con fechas y precio. Sigue activo. |
| `LEND_THING` | Préstamo. Con fechas. Sigue activo. |

### Things nuevos (F01–F15)

| Tipo | Colección | Descripción clave |
|------|-----------|-------------------|
| `SHARE_THING` | COMMUNITY | Al aceptar, la propiedad del thing pasa al solicitante. El nuevo dueño puede volver a compartirlo → cadena de transferencias. |
| `SWAP_THING` | `is_swap` | El solicitante ofrece sus propios things a cambio. Al aceptar, transferencia bilateral: ambas partes reciben lo que querían. |
| `EVENT_THING` | Cualquiera | Tiene `event_date`. Los invitados hacen toggle "Asistir / No asistir". Muestra contador de asistentes. |
| `WISH_THING` | COMMUNITY | S.O.S. comunitario. Los invitados hacen toggle "Puedo ayudar". Muestra contador de helpers. |
| `ASSET_THING` | Cualquiera | Activo compartido. Reserva por días (`DAY`) u horas (`HOUR`). Estadísticas de uso por mes. |
| `APPOINTMENT_THING` | Cualquiera | Cita con horario. Define `slot_duration` (15/30/60 min) y `availability_schedule` semanal. Vista de cuadrícula por semana. |

---

## Features implementadas

### F01 — Loan Chain + Community Collections (`82c7d7c`)
- **Modelo `ThingTransfer`**: registra cada traspaso físico (de quién, a quién, cuándo).
- **`Collection.mode`**: nuevo campo `PROPRIETARY` / `COMMUNITY`.
- **Endpoint `GET /api/v1/things/{code}/transfers/`**: historial y estadísticas agregadas.
- **Comando `close_transfers`**: cierra transferencias vencidas cada noche.
- **Tests**: `test_transfers.py` (93 líneas) + `test_community_collections.py` (220 líneas).

### F02 — Events / EVENT_THING (`07f91a3`)
- **`Thing.event_date`**: DateTimeField para la fecha del evento.
- **Endpoint `POST /api/v1/things/{code}/attend/`**: toggle de asistencia (usa M2M `deal`).
- **Endpoint `GET /api/v1/things/{code}/attendees/`**: lista de asistentes.
- **Email**: anuncio al crear el evento + recordatorio automático el día anterior.
- **Frontend**: tag "Event", contador de asistentes, botón toggle en ThingPage.
- **Tests**: `test_events.py` (176 líneas).

### F03 — S.O.S. / WISH_THING (`f593b73`)
- **Tipo `WISH_THING`**: solo en colecciones COMMUNITY.
- **Endpoint `POST /api/v1/things/{code}/offer-help/`**: toggle "Puedo ayudar".
- **Endpoint `GET /api/v1/things/{code}/helpers/`**: lista de helpers.
- **Frontend**: tag "Wish", contador de helpers, botón toggle en ThingPage.
- **Tests**: `test_wishes.py` (199 líneas).

### F04 — Broadcast a invitados (`11e40eb`)
- **Endpoint `POST /api/v1/collections/{code}/broadcast/`**: el dueño envía mensaje a todos los invitados. Límite 5/día.
- **Email**: con `Reply-To` al dueño para que los invitados respondan directamente.
- **Frontend**: botón "Enviar mensaje a invitados" en CollectionPage (solo dueño), formulario inline.
- **Tests**: `test_broadcast.py` (145 líneas).

### F05 — Recordatorios + Digests (`f978c0c`)
- **`Collection.digest_frequency`**: `NONE` / `WEEKLY` / `MONTHLY`.
- **Comando `send_reminders`**: recordatorios de devolución, entrega y evento (día anterior).
- **Comando `send_digests`**: resumen semanal (lunes) o mensual (día 1) con nuevas things.
- **Frontend**: selector de frecuencia en EditCollectionPage.
- **Tests**: `test_commands.py` (266 líneas).

### F06 — Shared Asset / ASSET_THING (`78ee2a3`)
- **`Thing.booking_unit`**: `DAY` o `HOUR` para granularidad de reserva.
- **`BookingPeriod.start_time` / `end_time`**: para reservas horarias.
- **Detección de solapamiento**: por rango horario en el mismo día.
- **Endpoint `GET /api/v1/things/{code}/stats/`**: uso por mes y usuario único.
- **Frontend**: selector DAY/HOUR en AddThingPage, formulario de hora en RequestThingPage, calendario compartido.
- **Tests**: `test_asset_things.py` (278 líneas).

### F07 — SHARE_THING + cadena de transferencias (`30a8f7c`)
- **Tipo `SHARE_THING`**: solo en COMMUNITY. Al aceptar, el `thing.owner` pasa al solicitante.
- **Lógica de ocultación**: tras la primera transferencia, solo el dueño de la colección puede ocultar el thing.
- **Frontend**: botón "Ocultar" condicionado a `collection_owner`.
- **Tests**: `test_share_transfer.py` (371 líneas).

### F08 — SWAP_THING + intercambio bilateral (`0ec0c7d`)
- **`Collection.is_swap`**: colección exclusiva de intercambios.
- **`BookingPeriod.offered_things`**: M2M con los things que el solicitante ofrece.
- **Transferencia bilateral**: al aceptar, las cosas viajan en ambas direcciones. ThingTransfer creado para cada una.
- **Emails específicos**: lista de things ofrecidos/recibidos en los emails de solicitud y confirmación.
- **Frontend**: checkboxes para seleccionar things propios al hacer la propuesta.
- **Tests**: `test_swap_things.py` (449 líneas).

### F09 — APPOINTMENT_THING + horarios (`3596a2b`)
- **`Thing.slot_duration`**: 15, 30 o 60 minutos.
- **`Thing.availability_schedule`**: JSONField con ventanas recurrentes por día de la semana.
- **Endpoint `GET /api/v1/things/{code}/slots/?week_start=YYYY-MM-DD`**: cuadrícula semanal de slots disponibles/ocupados.
- **Frontend**: `WeeklySchedule` component con navegación semanal, slots clicables.
- **Tests**: `test_appointments.py` (301 líneas).

### F10 — Markdown en descripciones (`b681151`)
- **Componente `MarkdownText`**: renderiza negrita, cursiva, listas y enlaces seguros.
- **Usado en**: ThingLinkbox (descripción), CollectionPage, ThingPage.
- **Seguridad**: HTML escapado antes de procesar. Solo URLs `http/https`.
- **Tests**: `markdown.test.jsx` (101 líneas con casos XSS).

### F11 — Documentos adjuntos (`7af340d`)
- **`Thing.documents`**: JSONField con hasta 5 documentos (PDF, Word, Excel, Markdown). Max 1 MB c/u.
- **Subida a Cloudinary** `raw` folder. URL de descarga enviada por email al aceptar la reserva.
- **Frontend**: componente `DocumentUpload` en AddThingPage y EditThingPage.
- **Tests**: `test_documents.py` (250 líneas).

### F12 — Modo SHARE exclusivo para comunidades (`389332b`)
- **`Collection.is_share`**: solo SHARE_THING permitido. Mutuamente exclusivo con `is_swap`.
- **Validaciones** a nivel de serializer y vista.
- **Frontend**: checkbox en CreateCollectionPage/EditCollectionPage (visible solo en COMMUNITY).
- **Tests**: `test_share_collections.py` (167 líneas).

### F13 — Timeline de transferencias para SHARE things (`af7417e`)
- **`is_share_in_community`**: flag calculado en ThingTransferStatsSerializer.
- **Frontend**: bloque "Sharing history" con "Originally shared by {name}" y contador de personas. CSS timeline dedicado.
- **Tests**: 84 líneas añadidas a `test_share_transfer.py`.

### F14 — Newsletter semanal para colecciones SHARE (`e01a068`)
- **`Collection.newsletter_enabled`**: requiere `is_share=True`. Envía boletín los lunes.
- **Contenido**: nuevas things de los últimos 7 días + cambios de propiedad (ThingTransfer).
- **Frontend**: checkbox en CreateCollectionPage/EditCollectionPage.
- **Tests**: `test_newsletter.py` (248 líneas).

### F15 — Skin minimalista / álbum de fotos (`7a140aa`)
- **`Collection.is_minimalist`**: álbum de fotos. Solo GIFT/SHARE/SWAP things. Thumbnail obligatorio.
- **ThingLinkbox minimalista**: foto a pantalla completa, caption en cursiva, botones mínimos.
- **Frontend**: checkbox en CreateCollectionPage/EditCollectionPage. Selector de tipo oculto en AddThingPage.
- **Tests**: `test_minimalist.py` (132 líneas).

---

## Cobertura de tests

### Backend

| Feature | Archivo | Líneas |
|---------|---------|--------|
| Loan Chain / Community | `test_transfers.py` + `test_community_collections.py` | 313 |
| Events | `test_events.py` | 176 |
| Wishes | `test_wishes.py` | 199 |
| Broadcast | `test_broadcast.py` | 145 |
| Reminders / Digests | `test_commands.py` | 266 |
| Asset Things | `test_asset_things.py` | 278 |
| Share Transfer | `test_share_transfer.py` | 371+84 |
| Swap Things | `test_swap_things.py` | 449 |
| Appointments | `test_appointments.py` | 301 |
| Documents | `test_documents.py` | 250 |
| Share Collections | `test_share_collections.py` | 167 |
| Newsletter | `test_newsletter.py` | 248 |
| Minimalist | `test_minimalist.py` | 132 |

**Total estimado: ~3.400 líneas de nuevos tests de integración.** Cobertura mínima del 80% enforced por CI.

### Frontend
- **`smoke.test.jsx`**: 17 páginas renderizadas con checks de accesibilidad axe.
- **`markdown.test.jsx`**: 101 líneas, cubre sintaxis y prevención XSS.
- ⚠️ No hay tests funcionales por componente (DocumentUpload, WeeklySchedule, etc.) — solo smoke.

---

## Lista para tests manuales en local

### 1. Community Collections (F01)
**Pasos iniciales:**
1. Inicia sesión como Lulu (lulu@mail.com).
2. Abre la colección "Phantom Shelf" → verifica que tiene modo COMMUNITY.
3. Inicia sesión como Lala en otra pestaña → entra a la colección de Lulu → añade una thing propia.
4. Comprueba que Lulu ve la thing de Lala en su colección.

### 2. Loan Chain / Transfer History (F01 + F07 + F13)
**Pasos iniciales:**
1. Lulu tiene un SHARE_THING activo → Lala lo solicita → Lulu acepta.
2. Ve a `/things/{code}/transfers/` → verifica que aparece el traspaso.
3. Ahora Lala es la nueva dueña → puede volver a compartirlo con Lolo.
4. Ve la "Sharing history" en ThingPage → verifica la cadena visual.

### 3. Events / EVENT_THING (F02)
**Pasos iniciales:**
1. Lolo crea un EVENT_THING en su colección con `event_date` futuro.
2. Lala ve el tag "Event" y el contador "0 attending".
3. Lala hace click en "Attend" → contador sube a 1.
4. Lala hace click de nuevo → vuelve a 0 (toggle).
5. Lolo ve la lista de asistentes.

### 4. S.O.S. / WISH_THING (F03)
**Pasos iniciales:**
1. Lulu crea un WISH_THING en una colección COMMUNITY (ej. "¿Alguien tiene un soporte de bici?").
2. Lala y Lolo ven el tag "Wish" y el botón "I can help".
3. Ambos hacen click → contador sube a 2.
4. Verifica que el dueño ve la lista de helpers.

### 5. Broadcast (F04)
**Pasos iniciales:**
1. Lulu (dueña) abre su colección → botón "Enviar mensaje a invitados".
2. Escribe asunto y mensaje → envía.
3. Verifica el email en Mailhog/console: asunto correcto, Reply-To = email de Lulu.
4. Intenta enviar 6 veces → comprueba el rate limit (5/día).

### 6. Digests (F05)
**Pasos iniciales:**
1. Configura una colección con `digest_frequency=WEEKLY`.
2. Ejecuta `python manage.py send_digests` manualmente.
3. Verifica que el email contiene las things añadidas en la última semana.

### 7. ASSET_THING por horas (F06)
**Pasos iniciales:**
1. Lili crea un ASSET_THING con `booking_unit=HOUR` (ej. "Furgoneta comunitaria").
2. Lala reserva de 09:00 a 11:00 el viernes.
3. Lolo intenta reservar de 10:00 a 12:00 el mismo día → debe dar error de solapamiento.
4. Lolo reserva de 12:00 a 14:00 → OK.
5. Ve las estadísticas en `/things/{code}/stats/`.

### 8. SWAP_THING (F08)
**Pasos iniciales:**
1. Crea una colección con `is_swap=True`.
2. Lala añade "Libro de cocina" (SWAP_THING). Lolo añade "Vinilo de jazz" (SWAP_THING).
3. Lala propone swap a Lolo: "Te doy mi libro a cambio de tu vinilo" → selecciona el libro como offered_thing.
4. Lolo acepta → verifica que ahora Lola tiene el vinilo y Lolo tiene el libro.
5. Comprueba ThingTransfer de ambos objetos.

### 9. APPOINTMENT_THING (F09)
**Pasos iniciales:**
1. Lolo crea un APPOINTMENT_THING (ej. "Clases de guitarra") con slots de 60 min, disponibilidad lunes y miércoles 10:00–14:00.
2. Lala ve la cuadrícula semanal → hace click en un slot disponible.
3. Se rellena automáticamente la fecha/hora en RequestThingPage → envía solicitud.
4. Lolo acepta → el slot queda marcado como "booked".
5. Otro usuario intenta el mismo slot → bloqueado.

### 10. Markdown en descripciones (F10)
**Pasos iniciales:**
1. Crea o edita una thing con descripción que incluya `**negrita**`, `*cursiva*`, `- lista`.
2. Ve el ThingLinkbox y ThingPage → verifica el renderizado.
3. Intenta poner `<script>alert(1)</script>` → verifica que se escapa.

### 11. Documentos adjuntos (F11)
**Pasos iniciales:**
1. Crea una thing (ej. RENT_THING o LEND_THING) y adjunta un PDF.
2. Verifica que aparece en EditThingPage.
3. Otro usuario reserva → el dueño acepta → verifica el email con el enlace de descarga.

### 12. Colección SHARE exclusiva (F12)
**Pasos iniciales:**
1. Crea una colección COMMUNITY + `is_share=True`.
2. Intenta añadir un LEND_THING → debe estar bloqueado (solo SHARE_THING).
3. Añade un SHARE_THING → OK.
4. Intenta activar `is_swap=True` al mismo tiempo → error de validación.

### 13. Newsletter semanal (F14)
**Pasos iniciales:**
1. Colección COMMUNITY + `is_share=True` + `newsletter_enabled=True`.
2. Añade una SHARE_THING y acepta una transferencia.
3. Ejecuta `python manage.py send_digests` un lunes (o cambia la lógica temporalmente).
4. Verifica el email: nueva thing + cambio de propiedad listados.

### 14. Skin minimalista (F15)
**Pasos iniciales:**
1. Crea una colección con `is_minimalist=True`.
2. Añade una thing (GIFT/SHARE/SWAP) con foto.
3. Verifica la UI de álbum: foto a pantalla completa, caption en cursiva, sin campos extra.
4. Intenta añadir una LEND_THING → bloqueado.
5. Intenta añadir una thing sin foto → bloqueado.

---

## Mejoras durante tests manuales (2026-04-21)

### M01 — Seed: libros de Lolo convertidos a EVENT_THING (`0064`)
- Migración `0064_update_lolo_books_to_event_things`: las 5 things del club de lectura de Lolo (`lltl06`–`lltl10`) convertidas a `EVENT_THING` con nuevos headlines ("Book Club session – …") y `event_date` programadas de enero a mayo de 2027, los días 5 de cada mes a las 16:00.

### M02 — UI de EVENT_THING: card y página de detalle
- **Tipo oculto**: la fila "Type" no se muestra en cards ni en ThingPage para eventos (redundante con el contexto).
- **Condición oculta**: la fila "Condition" tampoco se muestra para eventos.
- **Colon en "Event date"**: la etiqueta ahora muestra "Event date:" consistente con el resto de campos.
- **Asistentes reformateados**: icono cambiado a `IconGroup` (HDS), label "Attendees:" en bold a la izquierda, número plain a la derecha — mismo patrón que el resto de filas de info.
- Aplicado en `ThingLinkbox.jsx` y `ThingPage.jsx`.

### M03 — Email al owner cuando alguien se apunta o desapunta de un evento
- Nueva función `send_event_attend_email()` en `email_service.py`.
- Asunto y cuerpo distintos según `attending=True` ("signed up") o `attending=False` ("cancelled").
- Incluye fecha del evento si existe.
- Nombre del asistente cae a email cuando `user.name` está vacío.
- 3 nuevos tests en `TestEventAttendEmail` (apuntarse, desapuntarse, fallback a email).
- Docs actualizados: `core/services/CLAUDE.md` y `core/views/CLAUDE.md`.

---

## Notas antes del push

- ✅ Migraciones del `0052` al `0064` sin huecos.
- ✅ 16 tests de eventos pasando (13 originales + 3 nuevos de email).
- ⚠️ Los seeds actuales (Lili/Lolo/Lulu) usan los tipos de things clásicos y SHARE_THING básico. Hay que crear nuevos seeds completos antes de tests exhaustivos → ver `SEED_PLAN_F01_F15.md`.
- ⚠️ Los tests de frontend son solo smoke. No hay tests funcionales por componente.
