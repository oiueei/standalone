// Text legal de la instància — versió genèrica del repositori standalone.
// Cada desplegament d'OIUEEI té el seu propi operador, i aquest operador és el
// responsable del tractament de les dades: si auto-hospedes OIUEEI, edita la
// secció «Qui opera aquesta instància» amb la teva identitat i contacte.
// (El desplegament oficial www.oiueei.com substitueix aquest fitxer a la seva
// branca de desplegament per la versió completa, amb les dades reals del titular.)
export default `
# El nostre compromís

OIUEEI funciona sense publicitat i sense analítica de tercers: ningú no et rastreja mentre la fas servir. Les teves dades no són el producte — no es venen ni se cedeixen a ningú, mai. No hi ha píxels de seguiment als correus ni enllaços embolcallats amb rastrejadors. Aquest compromís està escrit a les regles de disseny del projecte i és el seu punt de partida, no la lletra petita.

# Qui opera aquesta instància

OIUEEI és programari de codi públic (llicència BUSL 1.1; MIT a partir de 2030). Aquesta pàgina descriu **una instància** d'OIUEEI: qui l'opera és el responsable del servei i del tractament de les teves dades.

*L'operador d'aquesta instància encara no ha completat aquesta secció amb la seva identitat i contacte. Si operes aquest desplegament, edita \`frontend/src/legal/\` amb les teves dades.*

# Privadesa

**Què desa l'aplicació, per disseny:** el teu email (per entrar amb enllaços màgics — sense contrasenyes), el teu nom i perfil opcional (bio, foto, idioma), el contingut que publiques (col·leccions, coses i les seves fotos, preguntes i respostes, reserves), les teves preferències de correu, i dades demogràfiques **opcionals** (generació de naixement i codi postal) que només veu qui administra les teves comunitats, en agregat — mai no són públiques.

**On van:** el correu surt pel proveïdor SMTP que l'operador hagi configurat i les imatges s'allotgen a Cloudinary. Res més no surt de la instància: sense SDKs de tercers, sense esdeveniments enviats enfora. Les mètriques d'ús són pròpies, pseudonimitzades i mai no es comparteixen.

**Cookies:** només tècniques (sessió i seguretat). No hi ha cookies de tercers ni de publicitat, per això no hi ha bàner.

**Esborrar el teu compte:** des del teu perfil (Editar perfil → Esborrar el compte), amb confirmació per correu. És immediat i irreversible: el teu compte, les teves col·leccions, les teves coses amb les seves fotos i les teves sol·licituds s'eliminen. Les preguntes que vas fer en coses d'altres persones i l'historial de mans es conserven **sense el teu nom** («Antic membre»).

# Termes bàsics

OIUEEI es troba en fase alfa i s'ofereix «tal com és», sense garanties, en la mesura que la llei ho permeti. El contingut que publiques és teu i n'ets responsable; no publiquis res il·legal o nociu. Els intercanvis (regals, vendes, préstecs, swaps) són acords entre persones: la plataforma no n'és part ni processa pagaments. Hi ha un botó per denunciar contingut, i l'operador pot retirar el que incompleixi aquestes normes.

# Per a operadors (self-hosting)

Si despleges OIUEEI, el responsable del tractament ets tu: completa aquesta pàgina amb la teva identitat, les teves finalitats i els teus encarregats (proveïdor de correu, Cloudinary, hosting), i atén els drets dels teus usuaris. La llicència BUSL 1.1 permet l'ús en producció; l'única cosa que no permet és oferir OIUEEI a tercers com a servei hospedat que competeixi amb l'oferta de pagament del llicenciant.
`;
