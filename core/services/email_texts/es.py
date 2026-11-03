"""Spanish email texts (``EMAIL_LANGUAGE=es``).

Same keys as ``en.py`` (guarded by the parity test); informal, warm tone,
matching the app's Spanish UI vocabulary (reservar, pedido, intercambio)."""

TEXTS = {
    # Shared
    "footer_manage": "Gestiona tus preferencias de correo",
    # Art. 14 RGPD: todo correo -- también los obligatorios -- enlaza a la
    # página legal: es una obligación de información, no una preferencia.
    "footer_legal": "Legal y privacidad",
    # How a booking's dates read inside a sentence: a range, or one day said once
    # ("from the 13th to the 13th" was a loan for a single day, 2026-10-02).
    "when_range": "del {start} al {end}",
    "when_day": "el {start}",
    "dates_label": "Fechas",
    # Cómo se nombra a alguien que nunca puso nombre, allí donde quien lee no
    # tiene derecho a su dirección. Ver "a_member" en en.py y `_member_name`.
    "a_member": "Un miembro",
    # The same stand-in in the middle of a sentence or a list (`_member_name(inline=True)`).
    "a_member_inline": "un miembro",
    "view_collection_cta": "Ver la colección",
    # Sustantivos de acción por tipo para los correos de reserva — calcan el
    # vocabulario del frontend (thingCard.action / types): una solicitud SELL
    # es "solicitud de compra", una LEND "solicitud de préstamo", etc.
    "action_noun_GIFT_THING": "regalo",
    "action_noun_SELL_THING": "compra",
    "action_noun_LEND_THING": "préstamo",
    "action_noun_RENT_THING": "alquiler",
    "action_noun_RESERVE_THING": "reserva",
    # Magic link
    "magic_subject": "¡Hola, te damos la bienvenida a OIUEEI!",
    "magic_subject_collection": "¡Hola, te damos la bienvenida a '{collection}' - OIUEEI!",
    # The greeting repeated at the top of the body — the inbox preview shows
    # only the subject, the body has to stand on its own (see send_magic_link_email).
    "magic_greeting": "¡Hola, te damos la bienvenida a OIUEEI!",
    "magic_greeting_collection": "¡Hola, te damos la bienvenida a '{collection}'!",
    "magic_plain": "Haz clic en el enlace para iniciar sesión: {link}",
    "magic_cta": "Iniciar sesión →",
    "cta_fallback": "Si prefieres, copia y pega este enlace en tu navegador:",
    # Shared by every CTA (one button or two) that has to spell its link out below it.
    "ctas_fallback": "Si prefieres, copia y pega estos enlaces en tu navegador:",
    # The one-line "what is this" under the OIUEEI parent title, for the one
    # email a reader may open with no idea what OIUEEI is.
    "generic_parent_pitch": (
        "Comparte lo que tienes con la gente que te rodea: un rastrillo para regalar o vender, "
        "una biblioteca de las cosas para prestar o alquilar, un taller para reservar por días "
        "o por horas. Después, invita a tu gente a pedir lo que necesite."
    ),
    # What a kind of collection is, one sentence each. The same words as
    # `kinds.<K>.what` in the frontend's locale files (the kind chooser): a shared
    # link's card uses them for a collection with no description of its own.
    # `test_kind_what_parity.py` keeps the two copies equal.
    "kind_what_STALL": "Cosas para vender o regalar: quien se la lleva, se la queda.",
    "kind_what_LIBRARY": "Cosas para prestar o alquilar: se las llevan a casa y las devuelven.",
    "kind_what_SHED": (
        "Máquinas y espacios que se usan donde están, con reserva por días o por horas."
    ),
    # Collection invite
    "invite_subject": "¡Tienes una invitación a '{collection}' - OIUEEI!",
    "invite_plain": (
        "Te han invitado a {collection}. "
        "Aceptar la invitación: {accept} | Rechazar la invitación: {reject}"
    ),
    "invite_intro": "{inviter} te ha invitado a este grupo.",
    "invite_recommended_by": "{proposer} te ha propuesto para este grupo.",
    "invite_accept_cta": "Aceptar la invitación",
    "invite_decline_cta": "Rechazar la invitación",
    # Art. 14 RGPD: este correo lo dio quien invita, no la persona invitada.
    "invite_source_note": (
        "Si has llegado aquí por una invitación, tu correo nos lo dio quien te "
        "invitó, y solo se usa para enviarte esta invitación. Si la rechazas o "
        "no haces nada, esa persona no podrá volver a invitarte por correo durante un año."
    ),
    # Collection access revoked
    "revoke_subject": "Tu acceso ha sido revocado",
    "revoke_plain": "{owner} ha revocado tu acceso a '{collection}'.",
    "revoke_intro": "{owner} ha revocado tu acceso a este grupo.",
    "revoke_outro": "Ya no podrás ver esta colección.",
    "revoke_things": "Tus cosas de este grupo se han borrado con tu salida: {things}.",
    "thing_left_subject": "«{thing}» ya no está en {group}",
    "thing_left_intro": (
        "Quien ofrecía «{thing}» ya no forma parte de {group}, "
        "y la cosa se ha ido con esa persona. "
        "Tu solicitud o reserva ya no sigue en pie."
    ),
    "thing_left_holding": "Si la tienes tú, devuélvesela como acordasteis.",
    "thing_withdrawn_subject": "Se ha retirado «{thing}» de {group}",
    "thing_withdrawn_intro": "Se ha retirado «{thing}» de {group}, y tu solicitud queda anulada.",
    # Collection welcome document (sent once, the first time someone joins)
    "welcome_doc_subject": "Te damos la bienvenida a '{collection}'",
    "welcome_doc_plain": (
        "Te damos la bienvenida a '{collection}'. El grupo tiene un documento de "
        "bienvenida y normas — échale un vistazo: {url}"
    ),
    "welcome_doc_intro": "¡Bienvenida! El grupo tiene un documento de bienvenida y normas:",
    "welcome_doc_link_label": "Abrir el documento",
    "welcome_doc_outro": "Échale un vistazo antes de empezar.",
    # Account deletion confirmation (right to erasure)
    "account_delete_subject": "¿Borrar tu cuenta de OIUEEI?",
    "account_delete_plain": (
        "Has pedido borrar tu cuenta de OIUEEI. Si confirmas, es inmediato e "
        "irreversible: tu cuenta, tus colecciones, tus cosas con sus fotos y tus "
        "solicitudes pendientes se borran para siempre. Las preguntas que hiciste "
        "sobre cosas de otras personas y el historial de cosas que pasaron por tus "
        "manos se conservan, sin tu nombre. Confirma aquí (el enlace funciona "
        "durante 24 horas): {link} — si no lo has pedido tú, ignora este correo y "
        "no pasará nada."
    ),
    "account_delete_intro": (
        "Has pedido borrar tu cuenta de OIUEEI. Este es el paso de confirmación — "
        "todavía no se ha borrado nada."
    ),
    "account_delete_deletes": (
        "Si confirmas, es inmediato e irreversible: tu cuenta, tus colecciones, tus "
        "cosas con sus fotos y tus solicitudes pendientes se borran para siempre."
    ),
    "account_delete_keeps": (
        "Las preguntas que hiciste sobre cosas de otras personas y el historial de "
        "cosas que pasaron por tus manos se conservan, sin tu nombre — se muestran "
        "como «antiguo miembro»."
    ),
    "account_delete_cta": "Confirmar el borrado",
    "account_delete_outro": (
        "El enlace funciona durante 24 horas y en la página confirmarás una vez "
        "más. Si no lo has pedido tú, ignora este correo — no pasará nada."
    ),
    # Aviso de inactividad (antes de borrar una cuenta sin usar)
    "inactivity_subject": "Tu cuenta de OIUEEI lleva tiempo en silencio",
    "inactivity_intro": (
        "Hace {months} meses que no entras en OIUEEI. No guardamos cuentas que nadie "
        "usa, así que este es el aviso que va antes."
    ),
    "inactivity_deletes": (
        "Dentro de {days} días tu cuenta desaparece, para siempre, y con ella tus "
        "colecciones, tus cosas y sus fotos."
    ),
    "inactivity_keep": "Con entrar una vez basta para conservarla. No hay que hacer nada más.",
    "inactivity_cta": "Entrar",
    "inactivity_outro": "Y si prefieres que se vaya, no tienes que hacer absolutamente nada.",
    "inactivity_plain": (
        "Hace {months} meses que no entras en OIUEEI, y no guardamos cuentas que nadie "
        "usa. Dentro de {days} días tu cuenta desaparece, para siempre, con tus "
        "colecciones, tus cosas y sus fotos. Con entrar una vez basta para "
        "conservarla: {link} — y si prefieres que se vaya, no tienes que hacer nada."
    ),
    # El mismo aviso para una cuenta que NO se va a borrar porque hay un grupo
    # que depende de ella. No puede amenazar con algo que no va a pasar.
    "inactivity_kept": (
        "Tu cuenta se queda: hay gente usando una colección tuya y no vamos a "
        "quitársela mientras tú no estás. Pero en todo este tiempo no la ha cuidado "
        "nadie, y es tuya."
    ),
    "inactivity_kept_outro": (
        "Si prefieres marcharte, puedes borrar tu cuenta tú, desde tu perfil, cuando quieras."
    ),
    "inactivity_kept_plain": (
        "Hace {months} meses que no entras en OIUEEI. Tu cuenta se queda —hay gente "
        "usando una colección tuya y no vamos a quitársela mientras tú no estás— pero "
        "en todo este tiempo no la ha cuidado nadie. Puedes retomarla aquí: {link} — o "
        "borrar tu cuenta tú, desde tu perfil, cuando quieras."
    ),
    # Contact form (support channel, to the operator)
    "contact_subject": "Contacto OIUEEI: {sender}",
    "collab_subject": "Colaboración OIUEEI: {sender}",
    "contact_plain": (
        "Alguien ha escrito por el formulario de contacto.\n\n"
        "Nombre: {name}\nEmail: {email}\n\n{message}"
    ),
    "contact_intro": "Alguien ha escrito por el formulario de contacto:",
    "contact_name_label": "Nombre",
    "contact_email_label": "Email",
    # Booking request (to owner)
    "booking_request_subject": "Tienes una solicitud de {action} pendiente",
    "booking_request_plain_dated": (
        "{requester} te ha enviado una solicitud de {action} para '{thing}' "
        "{when}. "
        "Confirmar la solicitud: {accept} | Rechazar la solicitud: {reject}"
    ),
    "booking_request_plain": (
        "{requester} te ha enviado una solicitud de {action} para '{thing}'. "
        "Confirmar la solicitud: {accept} | Rechazar la solicitud: {reject}"
    ),
    "booking_request_intro": "{requester} te ha enviado una solicitud de {action}:",
    # The requester's address travels with the request to whoever manages the thing:
    # shared by the request email and the reservation notice. There is no
    # sentence saying that "Reply" reaches them.
    "requester_email_label": "Email",
    "hold_confirm_cta": "Confirmar la solicitud",
    "hold_cancel_cta": "Rechazar la solicitud",
    # Booking decision (to requester)
    "decision_subject_confirmed": "Tu solicitud está confirmada",
    "decision_subject_cancelled": "Tu solicitud no ha salido adelante",
    "decision_confirmed": "confirmada",
    "decision_cancelled": "rechazada",
    "decision_plain_dated": (
        "Tu solicitud de {action} de '{thing}' {when} ha sido {decision}. Ver la publicación: {url}"
    ),
    "decision_plain": (
        "Tu solicitud de {action} de '{thing}' ha sido {decision}. Ver la publicación: {url}"
    ),
    "decision_by_confirmed": "{who} ha aceptado tu solicitud de {action}:",
    "decision_by_declined": "{who} ha rechazado tu solicitud de {action}:",
    "point_name_label": "Punto de recogida",
    "point_address_label": "Dirección",
    "point_hours_label": "Horario",
    "point_contact_label": "Contacto",
    "decision_intro": "Tu solicitud de {action} ha sido {decision}:",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "Tu invitación fue rechazada",
    "invite_rejected_plain": "{invitee} ha rechazado la invitación a '{collection}'.",
    "invite_rejected_intro": "{invitee} ha rechazado tu invitación a este grupo.",
    # Booking confirmation (to requester)
    "confirmation_subject": "Solicitud de {action} enviada",
    "confirmation_plain_dated": (
        "Tu solicitud de {action} para '{thing}' {when} se ha enviado. {outro} Ver la cosa: {url}"
    ),
    "confirmation_plain": (
        "Tu solicitud de {action} para '{thing}' se ha enviado. {outro} Ver la cosa: {url}"
    ),
    "confirmation_intro": "Tu solicitud de {action} se ha enviado:",
    # Who was told: one person who runs the thing, or more than one (a team) — the
    # person's name is not in it any more.
    "confirmation_outro_one": "Hemos avisado a quien gestiona esta cosa — te responderá pronto.",
    "confirmation_outro_other": (
        "Hemos avisado a quienes gestionan esta cosa — te responderán pronto."
    ),
    # Where the requester will be written to: the address they sign in with,
    # which the managers now hold. Said, never printed — the email already arrives there.
    "contact_shared_request": (
        "Tu email va con la solicitud: si hace falta, te escribirán aquí, al correo con el que "
        "entras en OIUEEI."
    ),
    # FAQ question (to owner)
    "faq_question_subject": "Hay una pregunta por responder",
    "faq_question_plain": (
        "{questioner} ha preguntado sobre '{thing}': {question} Ver la cosa: {url}"
    ),
    "faq_question_intro": "{questioner} ha hecho una pregunta sobre:",
    "question_label": "Pregunta",
    "faq_view_reply_cta": "Ver y responder",
    # FAQ answer (to questioner)
    "faq_answer_subject": "Tu pregunta ha sido respondida",
    "faq_answer_plain": "{owner} ha respondido: {answer}. Ver '{thing}': {url}",
    "faq_answer_intro": "{owner} ha respondido a tu pregunta sobre:",
    "your_question_label": "Tu pregunta",
    "reply_label": "Respuesta",
    # FAQ answer (to the rest of the managing team — not the answerer, not the asker)
    "faq_answered_team_subject": "Una pregunta sobre '{thing}' ya tiene respuesta",
    "faq_answered_team_plain": (
        "{answerer} ha respondido a una pregunta sobre '{thing}'. "
        "Respuesta: {answer} Ver la cosa: {url}"
    ),
    "faq_answered_team_intro": "{answerer} ha respondido a una pregunta sobre:",
    # FAQ hidden (to questioner)
    "faq_hide_subject": "Tu pregunta ha sido ocultada",
    "faq_hide_plain": "{owner} ha ocultado tu pregunta: {question}",
    "faq_hide_intro": "{owner} ha ocultado tu pregunta sobre:",
    # FAQ hidden (to the rest of the managing team — not the hider, not the asker)
    "faq_hidden_team_subject": "Se ha ocultado una pregunta sobre '{thing}'",
    "faq_hidden_team_plain": (
        "{hider} ha ocultado una pregunta sobre '{thing}'. Ver la cosa: {url}"
    ),
    "faq_hidden_team_intro": "{hider} ha ocultado una pregunta sobre:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Alguien ha denunciado una de tus cosas",
    "reported_plain": (
        "Alguien ha denunciado tu cosa '{thing}'. "
        "No compartimos quién lo denunció. Échale un vistazo: {url}"
    ),
    "reported_intro": "Alguien ha denunciado una de tus cosas:",
    "reported_outro": (
        "No compartimos quién lo denunció. Échale un vistazo y asegúrate de que todo está en orden."
    ),
    "reported_review_cta": "Revisar la cosa",
    "thing_hidden_subject": "{founder} ha ocultado una de tus cosas",
    "thing_hidden_plain": (
        "{founder} ha ocultado {thing} de {group}. Sigue siendo tuya: puedes volver a "
        "mostrarla cuando quieras. {url}"
    ),
    "thing_hidden_intro": "{founder} ha ocultado esta cosa de {group}:",
    "thing_hidden_outro": "Sigue siendo tuya: puedes volver a mostrarla cuando quieras.",
    "thing_hidden_cta": "Revisar la cosa",
    # Broadcast (owner → invitees)
    "email_note_test_subject": "Tu nota del correo, tal como la verán — {collection}",
    "email_note_test_intro": (
        "Así se verá tu nota en los correos que recibe quien pide algo en "
        "{collection}. Este solo te ha llegado a ti."
    ),
    "broadcast_subject": "¡Hey! {collection}",
    "broadcast_plain": "Mensaje de {owner}:\n\n{message}\n\nAbrir el grupo: {url}",
    "broadcast_intro": "{owner} ha enviado un mensaje al grupo:",
    "broadcast_open_cta": "Abrir el grupo",
    # Return reminder (to owner). "Vuelve" names what a loan does — "reserva" is
    # only RESERVE_THING, which never comes through this email.
    "reminder_subject": "Recordatorio: {thing} vuelve mañana",
    "reminder_plain": "Recordatorio: {requester} tiene que devolverte '{thing}' el {end}.",
    "reminder_body": "Recordatorio: {requester} tiene que devolverte {thing} el {end}.",
    "return_due_subject": "Mañana devuelves {thing}",
    "return_due_plain": "Un recordatorio amable: tienes que devolver '{thing}' a {owner} el {end}.",
    "return_due_body": "Un recordatorio amable: tienes que devolver {thing} a {owner} el {end}.",
    # Pickup reminders (LEND/RENT, start_date = tomorrow) — the day before the handover
    "pickup_due_subject": "Mañana recoges {thing}",
    "pickup_due_plain": "Un recordatorio amable: recoges '{thing}' de {owner} el {start}.",
    "pickup_due_body": "Un recordatorio amable: recoges {thing} de {owner} el {start}.",
    "pickup_reminder_subject": "Mañana entregas {thing}",
    "pickup_reminder_plain": "Recordatorio: {requester} recoge '{thing}' el {start}.",
    "pickup_reminder_body": "Recordatorio: {requester} recoge {thing} el {start}.",
    # Manual nudge from /owner-bookings: the return date has already passed
    "return_overdue_subject": "Recordatorio: devolver {thing}",
    "return_overdue_plain": (
        "{manager} te recuerda que '{thing}' tenía que volver el {end}. "
        "Si ya has hecho la devolución, puedes ignorar este correo."
    ),
    "return_overdue_body": (
        "{manager} te recuerda que {thing} tenía que volver el {end}. "
        "Si ya has hecho la devolución, puedes ignorar este correo."
    ),
    "view_thing_cta": "Ver la publicación",
    "demo_note": "Este grupo es de demostración: sus cosas y sus personas son de ejemplo.",
    # Reservas de espacio (RESERVE_THING) — confirmación automática, sin decisión
    "reservation_confirmed_subject": "Tu reserva de '{thing}' está confirmada",
    "reservation_confirmed_plain": (
        "Tu reserva de '{thing}' está confirmada {when}. Ver la publicación: {url}"
    ),
    "reservation_confirmed_intro": "Tu reserva está confirmada:",
    "contact_shared_reservation": "Tu email va con la reserva.",
    "reservation_fee_label": "Coste",
    "reservation_where_label": "Dónde",
    "reservation_notice_subject": "{requester} ha reservado '{thing}'",
    "reservation_notice_plain": "{requester} ha reservado '{thing}' {when}.",
    "reservation_notice_intro": "{requester} ha reservado:",
    "reservation_notice_phone": (
        "Ha dejado un teléfono de contacto: lo tienes en la página de reservas, "
        "hasta el día después de la reserva."
    ),
    "reservation_note_label": "Su mensaje",
    "reservation_cancelled_subject": "Reserva cancelada: '{thing}'",
    "reservation_cancelled_to_guest_plain": (
        "{other} ha cancelado tu reserva de '{thing}' ({when})."
    ),
    "reservation_cancelled_to_guest_intro": "{other} ha cancelado tu reserva de:",
    "reservation_cancelled_to_owner_plain": (
        "{other} ha cancelado su reserva de '{thing}' ({when})."
    ),
    "reservation_cancelled_to_owner_intro": "{other} ha cancelado su reserva de:",
    "reservation_cancel_confirmation_subject_self": "Tu reserva de '{thing}' está cancelada",
    "reservation_cancel_confirmation_subject_other": "Has cancelado una reserva de '{thing}'",
    "reservation_cancel_confirmation_intro_self": "Tu reserva está cancelada:",
    "reservation_cancel_confirmation_intro_other": "Has cancelado la reserva de {member}:",
    "reservation_cancel_confirmation_plain_self": (
        "Tu reserva de '{thing}' ({when}) está cancelada."
    ),
    "reservation_cancel_confirmation_plain_other": (
        "Has cancelado la reserva de {member} de '{thing}' ({when})."
    ),
    "reservation_reminder_subject": "Tu reserva de '{thing}' empieza mañana",
    "reservation_reminder_plain": (
        "Un recordatorio: tu reserva de '{thing}' es {when}. Ver la ficha: {url}"
    ),
    "reservation_reminder_intro": "Tu reserva empieza mañana:",
    # Digest
    "digest_subject": "Novedades en {collection}",
    "digest_plain": "Cosas nuevas:\n\n{things}\n\n{members}Ver la colección: {url}",
    "digest_new_members_one": "Y 1 persona nueva se ha sumado al grupo.",
    "digest_new_members_other": "Y {count} personas nuevas se han sumado al grupo.",
    "join_summary_subject_one": "Una persona nueva en {group}",
    "join_summary_subject_other": "{count} personas nuevas en {group}",
    "join_summary_intro_one": "Se ha unido a {group}: {names}.",
    "join_summary_intro_other": "Se han unido a {group}: {names}.",
    "join_summary_more": "y {count} más",
    "join_summary_cta": "Ver los miembros",
    "join_summary_and": "y",
    "digest_intro": "Cosas nuevas:",
    "proposal_subject": "{collection}: ¿invitamos a alguien?",
    "proposal_plain": (
        "{proposer} quiere invitar a alguien a {collection}:\n\n  {email}\n\n"
        "Todavía no hemos contactado con nadie: sólo ocurre si dices que sí.\n\n"
        "Invitarle: {approve}\nAhora no: {reject}"
    ),
    "proposal_intro": "{proposer} quiere invitar a alguien a {collection}.",
    "proposal_note": "Añade: {note}",
    "proposal_nobody_told": (
        "Todavía no hemos contactado con nadie. La invitación sólo se envía si dices que sí y, si"
        " dices que no, la persona propuesta nunca sabrá que lo fue."
    ),
    "proposal_approve_cta": "Invitarle",
    "proposal_reject_cta": "Ahora no",
    "proposal_declined_subject": "Sobre tu propuesta para {collection}",
    "proposal_declined_intro": (
        "Gracias por pensar en alguien para {collection}. {owner} ha "
        "decidido no enviar esa invitación por ahora:"
    ),
    "proposal_declined_outro": (
        "No hemos contactado con esta persona ni lo haremos. No cambia "
        "nada más: sigues formando parte del grupo."
    ),
    "proposal_declined_body": (
        "Gracias por pensar en alguien para {collection}. {owner} ha decidido no enviar esa "
        "invitación por ahora, así que no hemos contactado con {email} ni lo haremos. No cambia "
        "nada más: sigues formando parte del grupo."
    ),
    "digest_mute_cta": "Dejar de recibir los resúmenes de este grupo",
}


# Frases de crecimiento que se añaden a los correos salientes (encima del pie
# de preferencias) para convertir invitados en creadores. Se elige una al azar
# por envío. ``path`` es adonde lleva el CTA, bajo la URL base del frontend: el
# formulario del tipo del que habla la frase, o el selector (`/new`) si no habla
# de ninguno (una frase sin ``path`` lleva también ahí). Los mismos destinos en
# todos los idiomas; ``cta`` es solo la etiqueta del enlace.
VIRAL_LINES = [
    {
        "text": (
            "¿Renuevas el armario? Abre un rastrillo con la ropa que ya no usas y ofrécela a "
            "tus amigos."
        ),
        "cta": "Empieza aquí",
        "path": "/stall/new",
    },
    {
        "text": (
            "¿Un taladro que usas dos veces al año? Abre una biblioteca de las cosas con tus "
            "herramientas y préstalas a tus vecinos."
        ),
        "cta": "Abre tu biblioteca",
        "path": "/library/new",
    },
    {
        "text": (
            "¿Estanterías llenas de libros ya leídos? Ponlos en un rastrillo y dales una "
            "segunda vida."
        ),
        "cta": "Así de fácil",
        "path": "/stall/new",
    },
    {
        "text": (
            "¿Juguetes que se han quedado pequeños? Abre un rastrillo y pásalos a otras familias."
        ),
        "cta": "Crea el tuyo",
        "path": "/stall/new",
    },
    {
        "text": (
            "¿Mudanza a la vista? Abre un rastrillo con lo que no te llevas y encuéntrale "
            "nueva casa."
        ),
        "cta": "Empieza por aquí",
        "path": "/stall/new",
    },
    {
        "text": (
            "¿Un grupo de amigos, la escalera, el AMPA? Abrid juntos un rastrillo, una "
            "biblioteca de las cosas o un taller, y compartid entre todos."
        ),
        "cta": "Crea vuestro grupo",
        "path": "/new",
    },
]
