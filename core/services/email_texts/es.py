"""Spanish email texts (www.oiueei.com — ``EMAIL_LANGUAGE=es``).

Same keys as ``en.py`` (guarded by the parity test); informal, warm tone,
matching the app's Spanish UI vocabulary (reservar, pedido, intercambio)."""

TEXTS = {
    # Shared
    "footer_manage": "Gestiona tus preferencias de correo",
    "dates_label": "Fechas",
    "view_collection_cta": "Ver la colección",
    # Sustantivos de acción por tipo para los correos de reserva — calcan el
    # vocabulario del frontend (thingCard.action / types): una solicitud SELL
    # es "solicitud de compra", una LEND "solicitud de préstamo", etc. SWAP
    # tiene sus propias plantillas; WISH nunca reserva.
    "action_noun_GIFT_THING": "regalo",
    "action_noun_SELL_THING": "compra",
    "action_noun_LEND_THING": "préstamo",
    "action_noun_RENT_THING": "alquiler",
    "action_noun_SHARE_THING": "traspaso",
    # Magic link
    "magic_subject": "¡Hola, te damos la bienvenida a OIUEEI!",
    "magic_subject_collection": "¡Hola, te damos la bienvenida a '{collection}' - OIUEEI!",
    "magic_plain": "¡Hola! Haz clic aquí para iniciar sesión: {link}",
    "magic_intro": "¡Hola! Haz clic aquí para iniciar sesión:",
    "magic_cta": "Iniciar sesión",
    # Collection invite
    "invite_subject": "¡Tienes una invitación a '{collection}' - OIUEEI!",
    "invite_plain": (
        "Te han invitado a ver: {collection}. "
        "Aceptar la invitación: {accept} | Rechazar la invitación: {reject}"
    ),
    "invite_intro": "{inviter} te ha invitado a ver:",
    "invite_accept_cta": "Aceptar la invitación",
    "invite_decline_cta": "Rechazar la invitación",
    # Collection access revoked
    "revoke_subject": "Tu acceso ha sido revocado",
    "revoke_plain": "{owner} ha revocado tu acceso a '{collection}'.",
    "revoke_intro": "{owner} ha revocado tu acceso a:",
    "revoke_outro": "Ya no podrás ver esta colección.",
    # Booking request (to owner)
    "booking_request_subject": "Tienes una solicitud de {action} pendiente",
    "booking_request_plain_dated": (
        "{requester} te ha enviado una solicitud de {action} para '{thing}' "
        "del {start} al {end}. "
        "Confirmar la reserva: {accept} | Cancelar la reserva: {reject}"
    ),
    "booking_request_plain": (
        "{requester} te ha enviado una solicitud de {action} para '{thing}'. "
        "Confirmar la reserva: {accept} | Cancelar la reserva: {reject}"
    ),
    "booking_request_intro": "{requester} te ha enviado una solicitud de {action}:",
    "hold_confirm_cta": "Confirmar la reserva",
    "hold_cancel_cta": "Cancelar la reserva",
    # Booking decision (to requester)
    "decision_subject": "Tenemos noticias",
    "decision_confirmed": "confirmada",
    "decision_cancelled": "cancelada",
    "decision_plain_dated": (
        "Tu solicitud de {action} de '{thing}' del {start} al {end} ha sido {decision}."
    ),
    "decision_plain": "Tu solicitud de {action} de '{thing}' ha sido {decision}.",
    "decision_intro": "Tu solicitud de {action} ha sido {decision}:",
    # Booking auto-declined (someone else got it)
    "unavailable_subject": "Alguien llegó primero",
    "unavailable_plain": (
        "'{thing}' se ha ido con otra persona esta vez. "
        "No pasa nada — por aquí las cosas van y vienen, ¡mantente al tanto!"
    ),
    "unavailable_intro": "{thing} se ha ido con otra persona esta vez.",
    "unavailable_outro": "No pasa nada — por aquí las cosas van y vienen, ¡mantente al tanto!",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "Tu invitación fue rechazada",
    "invite_rejected_plain": "{invitee} ha rechazado la invitación a '{collection}'.",
    "invite_rejected_intro": "{invitee} ha rechazado tu invitación a:",
    # Booking confirmation (to requester)
    "confirmation_subject": "Solicitud de {action} enviada",
    "confirmation_plain_dated": (
        "Tu solicitud de {action} para '{thing}' del {start} al {end} se ha enviado. "
        "Hemos avisado a {owner} — te responderá pronto. "
        "Ver la cosa: {url}"
    ),
    "confirmation_plain": (
        "Tu solicitud de {action} para '{thing}' se ha enviado. "
        "Hemos avisado a {owner} — te responderá pronto. Ver la cosa: {url}"
    ),
    "confirmation_intro": "Tu solicitud de {action} se ha enviado:",
    "part_of_label": "Parte de",
    "confirmation_outro": "Hemos avisado a {owner} — te responderá pronto.",
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
    # FAQ hidden (to questioner)
    "faq_hide_subject": "Tu pregunta ha sido ocultada",
    "faq_hide_plain": "{owner} ha ocultado tu pregunta: {question}",
    "faq_hide_intro": "{owner} ha ocultado tu pregunta sobre:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Alguien ha denunciado uno de tus anuncios",
    "reported_plain": (
        "Alguien ha denunciado tu anuncio '{thing}'. "
        "No compartimos quién lo denunció. Échale un vistazo: {url}"
    ),
    "reported_intro": "Alguien ha denunciado uno de tus anuncios:",
    "reported_outro": (
        "No compartimos quién lo denunció. Échale un vistazo y asegúrate de que todo está en orden."
    ),
    "reported_review_cta": "Revisar el anuncio",
    # Broadcast (owner → invitees)
    "broadcast_subject": "¡Hey! {collection}",
    "broadcast_plain": "Mensaje de {owner} ({collection}):\n\n{message}\n\n¡Puedo ayudar! {url}",
    "broadcast_intro": "{owner} ha enviado un mensaje a {collection}:",
    "broadcast_help_cta": "¡Puedo ayudar!",
    # Wish posted (to group)
    "wish_posted_subject": "Alguien de tu grupo busca algo",
    "wish_posted_plain": (
        "{creator} ha publicado un nuevo pedido: '{wish}'. ¿Puedes ayudar? Míralo: {url}"
    ),
    "wish_posted_intro": "{creator} ha publicado un nuevo pedido:",
    "wish_posted_cta": "Mira si puedes ayudar",
    # Wish answered (to creator)
    "wish_response_subject": "Alguien ha contestado tu pedido",
    "wish_response_plain": "{responder} ha contestado tu pedido '{wish}'. Ver la respuesta: {url}",
    "wish_response_intro": "{responder} ha contestado tu pedido:",
    "wish_response_cta": "Ver la respuesta",
    # Wish resolved — thanks (to accepted responder)
    "wish_thanks_subject": "Gracias por tu ayuda",
    "wish_thanks_plain": (
        "{creator} ha marcado el pedido '{wish}' como resuelto "
        "y quería darte las gracias por tu ayuda."
    ),
    "wish_thanks_intro": "{creator} ha marcado este pedido como resuelto:",
    "wish_thanks_outro": "¡Gracias por echar una mano!",
    # Return reminder (to owner)
    "reminder_subject": "Recordatorio: una reserva termina mañana",
    "reminder_plain": "Recordatorio: la reserva de {requester} sobre '{thing}' termina el {end}.",
    "reminder_body": "Recordatorio: la reserva de {requester} sobre {thing} termina el {end}.",
    # Swap request (to owner)
    "swap_request_subject": "Tienes una propuesta de intercambio",
    "swap_request_plain": (
        "{requester} quiere intercambiar '{thing}' por: {offered}. "
        "Confirmar el intercambio: {accept} | Cancelar el intercambio: {reject}"
    ),
    "swap_request_intro": "{requester} quiere intercambiar:",
    "swap_exchange_label": "A cambio de:",
    "swap_confirm_cta": "Confirmar el intercambio",
    "swap_cancel_cta": "Cancelar el intercambio",
    # Swap confirmation (to requester)
    "swap_conf_subject": "Propuesta de intercambio enviada",
    "swap_conf_plain": (
        "Tu propuesta de intercambio de '{thing}' (ofreciendo: {offered}) ha sido enviada. "
        "Su dueño te responderá pronto."
    ),
    "swap_conf_sent": "¡Tu propuesta de intercambio ha sido enviada!",
    "swap_conf_requested_label": "Has pedido:",
    "swap_conf_offered_label": "Has ofrecido:",
    "swap_conf_outro": "Su dueño te responderá pronto.",
    # Digest
    "digest_subject": "Novedades en {collection}",
    "digest_plain": "Cosas nuevas en {collection}:\n\n{things}\n\nVer la colección: {url}",
    "digest_intro": "Cosas nuevas en {collection}:",
    # Newsletter
    "newsletter_subject": "Boletín semanal: {collection}",
    "newsletter_intro": "Boletín de {collection}:",
    "newsletter_new_things": "Cosas nuevas",
    "newsletter_transfers": "Cambios de dueño",
}

# Frases de crecimiento que se añaden a los correos salientes (encima del pie
# de preferencias) para convertir invitados en creadores. Se elige una al azar
# por envío. El CTA siempre apunta a {frontend_base}/collections/new; ``cta``
# es solo la etiqueta del enlace.
VIRAL_LINES = [
    {
        "text": (
            "¿Renuevas el armario? Crea una colección con la ropa que ya no usas "
            "y ofrécela a tus amigos."
        ),
        "cta": "Empieza aquí",
    },
    {
        "text": (
            "¿Un taladro que usas dos veces al año? Crea una colección con tus "
            "herramientas y préstalas a tus vecinos."
        ),
        "cta": "Crea tu colección",
    },
    {
        "text": (
            "¿Estanterías llenas de libros ya leídos? Móntales una colección y "
            "dales una segunda vida."
        ),
        "cta": "Así de fácil",
    },
    {
        "text": (
            "¿Juguetes que se han quedado pequeños? Crea una colección y pásalos a otras familias."
        ),
        "cta": "Crea la tuya",
    },
    {
        "text": (
            "¿Mudanza a la vista? Haz una colección con lo que no te llevas y "
            "encuéntrale nueva casa."
        ),
        "cta": "Empieza por aquí",
    },
    {
        "text": (
            "¿Un grupo de amigos, la escalera, el AMPA? Cread una colección "
            "comunitaria y compartid entre todos."
        ),
        "cta": "Crea vuestro grupo",
    },
]
