// Text legal de la instància — versió genèrica del repositori standalone.
// Cada desplegament d'OIUEEI té el seu propi operador, i aquest operador és el
// responsable del tractament de les dades: si auto-hospedes OIUEEI, edita la
// secció «Qui opera aquesta instància» amb la teva identitat i contacte.
// (Un desplegament pot substituir aquest fitxer pel seu propi text, amb les
// dades reals del titular.)
export default `
# El nostre compromís

OIUEEI funciona sense publicitat i sense analítica de tercers: ningú no et rastreja mentre la fas servir. Les teves dades no són el producte — no es venen ni se cedeixen a ningú, mai. No hi ha píxels de seguiment als correus ni enllaços embolcallats amb rastrejadors. Aquest compromís està escrit a les regles de disseny del projecte i és el seu punt de partida, no la lletra petita.

# Qui opera aquesta instància

OIUEEI és programari de codi obert (llicència EUPL-1.2). Aquesta pàgina descriu **una instància** d'OIUEEI: qui l'opera és el responsable del servei i del tractament de les teves dades.

*L'operador d'aquesta instància encara no ha completat aquesta secció amb la seva identitat i contacte. Si operes aquest desplegament, edita \`frontend/src/legal/\` amb les teves dades.*

# Privadesa

**Què desa l'aplicació, per disseny:** el teu email (per entrar amb enllaços màgics — sense contrasenyes), el teu nom i perfil opcional (bio, foto, idioma), el contingut que publiques (col·leccions, coses i les seves fotos, preguntes i respostes, reserves), les teves preferències de correu, i dades demogràfiques **opcionals** (generació de naixement i codi postal) que només veu qui administra les teves comunitats, en agregat — mai no són públiques.

**El que comptem (només números):** cada dia, quantes persones amb sessió van fer servir l'app des d'un mòbil i quantes des d'un altre dispositiu (un ordinador o una tauleta), i quantes vegades es va desar una col·lecció o una cosa des de cadascun. Només guardem aquests números: ni qui, ni les dades del teu navegador.

**On van:** el correu surt pel proveïdor SMTP que l'operador hagi configurat i les imatges i els documents es desen al bucket d'emmagatzematge d'objectes del mateix operador. Res més no surt de la instància: sense SDKs de tercers, sense esdeveniments enviats enfora. Les mètriques d'ús són pròpies, pseudonimitzades i mai no es comparteixen.

**Qui veu què dins d'un grup:** una sol·licitud que fas sobre una cosa (un préstec, un lloguer, un regal, una compra o una reserva) arriba a qui gestiona aquesta cosa —el seu propietari i, en un grup que porta un equip, les persones que el dinamitzen— amb el teu nom i el teu email, perquè et puguin respondre. Si el grup ho demana en reservar, també pots deixar un telèfon de contacte: és opcional, només el veu qui gestiona aquesta reserva i s'esborra l'endemà de la reserva. Una pregunta que fas en una cosa s'hi mostra amb el teu nom a qui hagi entrat amb el seu compte i pugui veure la cosa, tret que qui la gestiona l'amagui. Quan s'accepta un préstec, un lloguer, un regal o una venda, l'historial de la cosa mostra el teu nom de la mateixa manera (tret d'un regal o una venda marcats com a «il·limitat», que no deixen historial). Qui dinamitza un grup també pot descarregar-ne el calendari, amb el nom de cada reserva, préstec o lloguer. El teu email només arriba a l'altra banda quan tu li escrius: un missatge que envies als membres d'un grup, o un recordatori perquè tornin alguna cosa, permet a qui el rep respondre't, així que veu la teva adreça.

**Cookies:** només tècniques (sessió i seguretat). No hi ha cookies de tercers ni de publicitat, per això no hi ha bàner.

**Esborrar el teu compte:** des del teu perfil (Editar perfil → Esborrar el compte), amb confirmació per correu. És immediat i irreversible: el teu compte, les teves col·leccions, les teves coses amb les seves fotos i les teves sol·licituds s'eliminen. Les preguntes que vas fer en coses d'altres persones i l'historial de mans es conserven **sense el teu nom** («Antic membre»).

**Emportar-te una còpia de les teves dades:** també en autoservei, des del teu perfil — descarrega-ho tot en un fitxer, quan vulguis, sense confirmació per correu. Si administres un grup, també pots descarregar el grup sencer: membres, coses, tot l'historial. Aquest segon fitxer porta dades d'altres persones, així que desa'l bé i no el reenviïs.

# Termes bàsics

OIUEEI es troba en fase alfa i s'ofereix «tal com és», sense garanties, en la mesura que la llei ho permeti. El contingut que publiques és teu i n'ets responsable; no publiquis res il·legal o nociu. Els intercanvis (regals, vendes, préstecs, lloguers, reserves d'espai) són acords entre persones: la plataforma no n'és part ni processa pagaments — una fiança que aparegui en una fitxa és informació que acorden les dues persones entre elles, i OIUEEI mai no la reté, la mou ni en garanteix la devolució. Hi ha un botó per denunciar contingut, i l'operador pot retirar el que incompleixi aquestes normes.

# Per a operadors (self-hosting)

Si despleges OIUEEI, el responsable del tractament ets tu: completa aquesta pàgina amb la teva identitat, les teves finalitats i els teus encarregats (proveïdor de correu, emmagatzematge d'objectes, hosting), i atén els drets dels teus usuaris. La llicència EUPL-1.2 permet l'ús en producció; el que demana a canvi és reciprocitat — si ofereixes un OIUEEI modificat com a servei, has de posar el seu codi font a disposició dels teus usuaris sota la mateixa llicència.
`;
