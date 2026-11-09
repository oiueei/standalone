// Texto legal de la instancia — versión genérica del repositorio standalone.
// Cada despliegue de OIUEEI tiene su propio operador, y ese operador es el
// responsable del tratamiento de los datos: si auto-hospedas OIUEEI, edita la
// sección «Quién opera esta instancia» con tu identidad y contacto.
// (Un despliegue puede sustituir este archivo por su propio texto, con los
// datos reales de su titular.)
export default `
# Nuestro compromiso

OIUEEI funciona sin publicidad y sin analítica de terceros: nadie te rastrea mientras la usas. Tus datos no son el producto — no se venden ni se ceden a nadie, nunca. No hay píxeles de seguimiento en los correos ni enlaces envueltos en rastreadores. Este compromiso está escrito en las reglas de diseño del proyecto y es su punto de partida, no la letra pequeña.

# Quién opera esta instancia

OIUEEI es software de código abierto (licencia EUPL-1.2). Esta página describe **una instancia** de OIUEEI: quien la opera es el responsable del servicio y del tratamiento de tus datos.

*El operador de esta instancia aún no ha completado esta sección con su identidad y contacto. Si operas este despliegue, edita \`frontend/src/legal/\` con tus datos.*

# Privacidad

**Qué guarda la aplicación, por diseño:** tu email (para entrar con enlaces mágicos — sin contraseñas), tu nombre y perfil opcional (bio, foto, idioma), el contenido que publicas (colecciones, cosas y sus fotos, preguntas y respuestas, reservas), tus preferencias de correo, y datos demográficos **opcionales** (generación de nacimiento y código postal) que solo ve quien administra tus comunidades, en agregado — nunca son públicos.

**Lo que contamos (solo números):** cada día, cuántas personas con sesión usaron la app desde un móvil y cuántas desde otro dispositivo (un ordenador o una tableta), y cuántas veces se guardó una colección o una cosa desde cada uno. Solo guardamos esos números: ni quién, ni los datos de tu navegador.

**A dónde van:** el correo sale por el proveedor SMTP que el operador haya configurado y las imágenes y documentos se guardan en el bucket de almacenamiento de objetos del propio operador. Nada más sale de la instancia: sin SDKs de terceros, sin eventos enviados fuera. Las métricas de uso son propias, seudonimizadas y nunca se comparten.

**Quién ve qué dentro de un grupo:** una solicitud que haces sobre una cosa (un préstamo, un alquiler, un regalo, una compra o una reserva) le llega a quien gestiona esa cosa —su dueño y, en un grupo que lleva un equipo, quienes lo dinamizan— con tu nombre y tu email, para que puedan responderte. Si el grupo lo pide al reservar, puedes dejar también un teléfono de contacto: es opcional, solo lo ve quien gestiona esa reserva y se borra el día después de la reserva. Una pregunta que haces en una cosa se muestra en ella con tu nombre a quien haya entrado con su cuenta y pueda ver la cosa, salvo que quien la gestiona la oculte. Cuando se acepta un préstamo, un alquiler, un regalo o una venta, el historial de la cosa muestra tu nombre de la misma forma (salvo en un regalo o una venta marcados como «sin límite», que no dejan historial). Quien dinamiza un grupo también puede descargar su calendario, con el nombre de cada reserva, préstamo o alquiler. Tu email solo le llega al otro lado cuando tú le escribes: un mensaje que envías a los miembros de un grupo, o un recordatorio para que devuelvan algo, permite a quien lo recibe responderte, así que ve tu dirección. Tu perfil (nombre, frase, bio y foto) lo ve quien comparte algún grupo contigo, nunca tu email, tu idioma ni tus datos demográficos. Quien dinamiza un grupo puede tener en él una página con el nombre de su entidad, un logo, una presentación y un contacto (y, en una red, la dirección y el horario de su punto de recogida): se ve junto con el grupo, también sin cuenta si el grupo es público. Si alguien te invita por email, el grupo guarda durante un año una huella de tu dirección (no la dirección) para no volver a invitarte; se borra pasado ese año.

**Cookies:** solo técnicas (sesión y seguridad). No hay cookies de terceros ni de publicidad, por eso no hay banner.

**Borrar tu cuenta:** desde tu perfil (Editar perfil → Borrar cuenta), con confirmación por correo. Es inmediato e irreversible: tu cuenta, tus colecciones, tus cosas y sus fotos y tus solicitudes se eliminan. Las preguntas que hiciste en cosas de otras personas y el historial de manos se conservan **sin tu nombre** («Antiguo miembro»).

**Llevarte una copia de tus datos:** también en autoservicio, desde tu perfil — descarga todo en un fichero, cuando quieras, sin confirmación por correo. Si administras un grupo, también puedes descargar el grupo entero: miembros, cosas, todo el historial. Ese segundo fichero lleva datos de otras personas, así que guárdalo bien y no lo reenvíes.

# Términos básicos

OIUEEI se encuentra en fase alfa y se ofrece «tal cual», sin garantías, en la medida en que la ley lo permita. El contenido que publicas es tuyo y respondes de él; no publiques nada ilegal o dañino. Los intercambios (regalos, ventas, préstamos, alquileres, reservas de espacio) son acuerdos entre personas: la plataforma no es parte de ellos ni procesa pagos — una fianza que aparezca en una ficha es información que acuerdan las dos personas entre sí, y OIUEEI nunca la retiene, la mueve ni garantiza su devolución. Existe un botón para denunciar contenido, y el operador puede retirar lo que incumpla estas normas.

# Para operadores (self-hosting)

Si despliegas OIUEEI, el responsable del tratamiento eres tú: completa esta página con tu identidad, tus finalidades y tus encargados (proveedor de correo, almacenamiento de objetos, hosting), y atiende los derechos de tus usuarios. La licencia EUPL-1.2 permite el uso en producción; lo que pide a cambio es reciprocidad — si ofreces un OIUEEI modificado como servicio, debes poner su código fuente a disposición de tus usuarios bajo la misma licencia.
`;
