// Texto legal de la instancia — versión genérica del repositorio standalone.
// Cada despliegue de OIUEEI tiene su propio operador, y ese operador es el
// responsable del tratamiento de los datos: si auto-hospedas OIUEEI, edita la
// sección «Quién opera esta instancia» con tu identidad y contacto.
// (El despliegue oficial www.oiueei.com sustituye este archivo en su rama de
// despliegue por la versión completa, con los datos reales de su titular.)
export default `
# Nuestro compromiso

OIUEEI funciona sin publicidad y sin analítica de terceros: nadie te rastrea mientras la usas. Tus datos no son el producto — no se venden ni se ceden a nadie, nunca. No hay píxeles de seguimiento en los correos ni enlaces envueltos en rastreadores. Este compromiso está escrito en las reglas de diseño del proyecto y es su punto de partida, no la letra pequeña.

# Quién opera esta instancia

OIUEEI es software de código público (licencia BUSL 1.1; MIT a partir de 2030). Esta página describe **una instancia** de OIUEEI: quien la opera es el responsable del servicio y del tratamiento de tus datos.

*El operador de esta instancia aún no ha completado esta sección con su identidad y contacto. Si operas este despliegue, edita \`frontend/src/legal/\` con tus datos.*

# Privacidad

**Qué guarda la aplicación, por diseño:** tu email (para entrar con enlaces mágicos — sin contraseñas), tu nombre y perfil opcional (bio, foto, idioma), el contenido que publicas (colecciones, cosas y sus fotos, preguntas y respuestas, reservas), tus preferencias de correo, y datos demográficos **opcionales** (generación de nacimiento y código postal) que solo ve quien administra tus comunidades, en agregado — nunca son públicos.

**A dónde van:** el correo sale por el proveedor SMTP que el operador haya configurado y las imágenes se alojan en Cloudinary. Nada más sale de la instancia: sin SDKs de terceros, sin eventos enviados fuera. Las métricas de uso son propias, seudonimizadas y nunca se comparten.

**Cookies:** solo técnicas (sesión y seguridad). No hay cookies de terceros ni de publicidad, por eso no hay banner.

**Borrar tu cuenta:** desde tu perfil (Editar perfil → Borrar cuenta), con confirmación por correo. Es inmediato e irreversible: tu cuenta, tus colecciones, tus cosas y sus fotos y tus solicitudes se eliminan. Las preguntas que hiciste en cosas de otras personas y el historial de manos se conservan **sin tu nombre** («Antiguo miembro»).

# Términos básicos

OIUEEI se encuentra en fase alfa y se ofrece «tal cual», sin garantías, en la medida en que la ley lo permita. El contenido que publicas es tuyo y respondes de él; no publiques nada ilegal o dañino. Los intercambios (regalos, ventas, préstamos, swaps) son acuerdos entre personas: la plataforma no es parte de ellos ni procesa pagos. Existe un botón para denunciar contenido, y el operador puede retirar lo que incumpla estas normas.

# Para operadores (self-hosting)

Si despliegas OIUEEI, el responsable del tratamiento eres tú: completa esta página con tu identidad, tus finalidades y tus encargados (proveedor de correo, Cloudinary, hosting), y atiende los derechos de tus usuarios. La licencia BUSL 1.1 permite el uso en producción; lo único que no permite es ofrecer OIUEEI a terceros como servicio hospedado que compita con la oferta de pago del licenciante.
`;
