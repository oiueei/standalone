"""
Catalan demo-data text. Merged onto the structural skeleton in common.py by
`seed_demo.load_seed_data`. Collection/thing text is always seeded in every
language at once (localized {lang: text} maps); `--lang=ca` selects this
file for the NON-localizable rest: user bios and FAQs.

Text lengths respect model max_length (headline=64, description=256,
question=64, answer=256) — per language.
"""

USERS = [
    {
        "code": "La1aN1",
        "headline": "Visca la segona mà!",
        "about": "## Hola, soc la Lala! 👋\n\nDevota de la **segona mà** de tota la vida — el que a un li sobra, a un altre li fa il·lusió. Ara buido el pis abans d'un *sabàtic*, així que tot ha de sortir!\n\n- ♻️ Reutilitzar abans que comprar\n- 🤝 Efectiu, recollida i bon rotllo",
    },
    {
        "code": "L3L3oo",
        "headline": "Els diumenges munto mercadet i dinar a la cooperativa.",
        "about": "## Diumenges a la cooperativa 🥘\n\nVisc en una **cooperativa d'habitatge**, i aquí gairebé res no es fa en solitari. Cada diumenge muntem al pati un **mercadet-festa-dinar**: cadascú baixa el que li sobra, algú posa música i sempre acaba havent-hi més menjar que gent.\n\n- 🧺 El que a tu et sobra, a la veïna li fa falta\n- 🔧 Eines compartides, escala inclosa\n- 🍲 Porta plat, te'n vas amb recepta",
    },
    {
        "code": "l1l13S",
        "headline": "Visca la botiga de préstecs! La Lili ho presta gairebé tot.",
        "about": "## Demana en préstec, no compris 🤝\n\nGuardiana de la **biblioteca del barri**: de trepants i vaporetes a coses de cuina, jardí, esport i criança. Si només ho faràs servir de tant en tant, millor demana-m'ho. Reutilitzar abans que comprar!",
    },
    {
        "code": "l0l0oh",
        "headline": "Esqueixos gratis al saló verd d'en Lolo.",
        "about": "## El saló verd 🌿\n\nMassa cries de **suculenta** a l'ampit — echeveries, jades i sèdums buscant llar. Passa a buscar un esqueix gratis, amb guia de cures inclosa. Única regla: posa-li nom a la teva nova amiga verda!",
    },
    {
        "code": "1u1ucs",
        "headline": "Conec tothom i m'apunto a tot – l'espurna de la comunitat!",
        "about": "## L'espurna de la comunitat ✨\n\nConec tothom i m'apunto a tot. Si algú del barri presta, regala o ven alguna cosa, *ja hi soc* — i te n'aviso. Si passa alguna cosa, me n'assabento la primera.",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "headline": "DEMO · La Lala se'n va de sabàtic: tot es ven per deu peles!",
        "description": "Tres regles, company: només efectiu, ho reculls tu, data límit el 25. Queda res? Directe a l'orfenat del barri!",
    },
    {
        "code": "l0l0C1",
        "headline": "DEMO · El saló verd d'en Lolo – emporta't una suculenta gratis!",
        "description": "Passa a conèixer el meu esquadró suculent – echeveries, jades, sèdums – i et regalo un esqueix. Guia fàcil de cures inclosa. Única regla: posa-li nom a la teva nova amiga verda!",
    },
    {
        "code": "l1l1C1",
        "headline": "DEMO · Préstecs de la Lili – hora de compartir les coses!",
        "description": "Necessites trepant, vaporeta, escala sòlida, bàscula d'equipatge o un mega kit de magdalenes? La biblioteca de préstecs de la Lili t'ho cobreix – tot a un cost simbòlic!",
    },
    {
        "code": "1u1uC1",
        "headline": "DEMO · Eines per a nosaltres!",
        "description": "Pugem aquí les eines que tenim i les posem a disposició de la resta del grup. Cuideu-les bé: són nostres i les necessitem entre totes i tots.",
    },
    {
        "code": "L3L3C1",
        "headline": "DEMO · El mercadet dels diumenges al pati",
        "description": "Cada diumenge muntem mercadet, festa i dinar al pati. Baixa el que ja no facis servir i emporta't el que et faci falta: aquí tot es regala. Només per a veïnes i veïns de la cooperativa.",
    },
    {
        "code": "1u1uRe",
        "headline": "DEMO · El taller de la Lulu — reserva un lloc",
        "description": "Reserva un banc o el racó de reunions per usar-lo aquí, al taller. És teu per un dia (o fins a tres), res no surt de la sala i la reserva es confirma a l'instant. Obert de dilluns a divendres.",
    },
    {
        "code": "N3t0C1",
        "headline": "DEMO · La Xarxa de Préstec: cada entitat presta el que és seu",
        "description": "Diverses entitats presten des d'un mateix prestatge. Cada una té les seves coses, el seu punt de recollida i el seu horari: mira qui presta què i recull-ho on t'indiquin.",
    },
]

THINGS = [
    {
        "code": "La1a01",
        "headline": "Catifa nòrdica peluda",
        "description": "Niu de meditació nòrdic! Llana suau com una ovella escocesa, vibracions hygge amb aroma de patxuli. Per només deu peles!",
    },
    {
        "code": "La1a02",
        "headline": "Joc de tasses",
        "description": 'Festa del te pagana! 12 tasses amb "Keep Calm and Chai On". Perfectes per a infusions hippies!',
    },
    {
        "code": "La1a03",
        "headline": "Batedora retro",
        "description": "Batedora McBatedora! Aquest trasto màgic tritura kale i somnis hippies en batuts còsmics. Pau i suc per deu peles!",
    },
    {
        "code": "La1a04",
        "headline": "Planxa de vapor",
        "description": "Doma arrugues com una bèstia! Deixa les samarretes tie-dye impecables per als festivals. Suavitza el teu karma per deu peles!",
    },
    {
        "code": "La1a05",
        "headline": "Làmpada psicodèlica disco",
        "description": "Garlanda rasta! Gira com un viatge de Glastonbury, brilla per a infusions de mitjanit. Mola per deu peles!",
    },
    {
        "code": "l1l101",
        "headline": "Tren de cartró per jugar",
        "description": "Tren gegant de cartró fet a mà. Ideal per a festes, jocs imaginatius o photocall infantil. Es munta i es desmunta fàcil. Una peça molt original per als menuts.",
    },
    {
        "code": "l1l102",
        "headline": "Circuit de tren de fusta",
        "description": "Circuit infantil de tren musical amb peces encaixables i passaboles. Fusta resistent i colorida. Estimula la motricitat i el joc. Perfecte per a primeres edats.",
    },
    {
        "code": "l1l103",
        "headline": "Tres en ratlla artesanal",
        "description": "Joc de tres en ratlla fet amb xapes i cartró. Lleuger, divertit i fàcil de transportar. Per jugar a casa o de viatge. Diversió senzilla per a totes les edats.",
    },
    {
        "code": "l1l104",
        "headline": "Caseta infantil amb taula",
        "description": "Caseta de joc de plàstic amb porta, finestres, taula i bancs. Resistent per a interior o jardí. Hores de joc simbòlic per als menuts. Fàcil de netejar.",
    },
    {
        "code": "l1l105",
        "headline": "Laberint de bales",
        "description": "Laberint de bales fet a mà amb cartró i bastonets de colors. Posa a prova el pols i la paciència. Un clàssic que enganxa grans i petits.",
    },
    {
        "code": "l1l106",
        "headline": "Jardinera vertical de paret",
        "description": "Set de jardineres verticals apilables per penjar a la paret. Perfectes per a herbes aromàtiques o plantes petites en balcons i terrasses. Aprofita l'espai.",
    },
    {
        "code": "l1l107",
        "headline": "Impressora làser HP LaserJet",
        "description": "Impressora làser HP LaserJet en blanc i negre. Fiable per a documents puntuals o impressions ràpides. A punt per fer servir. Ideal si només imprimeixes de tant en tant.",
    },
    {
        "code": "l1l108",
        "headline": "Consola Nintendo Game Boy",
        "description": "Consola portàtil Nintendo Game Boy clàssica. Pura nostàlgia per jugar als títols de sempre. Funciona amb piles. Una joia retro per fer unes partides.",
    },
    {
        "code": "l1l109",
        "headline": "Fregona giratòria amb cubell",
        "description": "Fregona giratòria amb cubell centrifugador. Escorre sense esforç i deixa el terra gairebé sec. Còmoda i eficaç per a la neteja del dia a dia. Mànec extensible.",
    },
    {
        "code": "l1l110",
        "headline": "Netejador de vapor de mà",
        "description": "Netejador de vapor portàtil amb accessoris. Desinfecta sense productes químics en banys, cuines i juntes. Pràctic per a neteges a fons puntuals. Fàcil de fer servir.",
    },
    {
        "code": "l1l111",
        "headline": "Aspirador sec i humit",
        "description": "Aspirador de sòlids i líquids amb rodes i accessoris. Potent per a garatges, cotxes, reformes o vessaments. Dipòsit ampli d'acer. Per al que una aspiradora normal no pot.",
    },
    {
        "code": "l1l112",
        "headline": "Trepant cargolador Ryobi",
        "description": "Trepant cargolador a bateria Ryobi. Per muntar mobles, penjar quadres o petites reformes a casa. Lleuger i manejable. Inclou bateria. Perfecte per al bricolatge bàsic.",
    },
    {
        "code": "l1l113",
        "headline": "Kit d'eines bàsiques",
        "description": "Maletí d'eines per al bricolatge: martell, tornavisos, alicates, clau, nivell i cinta mètrica. L'essencial per a arranjaments i muntatges a casa. Ben organitzat.",
    },
    {
        "code": "l1l114",
        "headline": "Roda abdominal",
        "description": "Roda per exercitar abdominals i core a casa. Compacta i resistent amb agafadors encoixinats. Ideal per entrenar força sense anar al gimnàs. Fàcil de guardar.",
    },
    {
        "code": "l1l115",
        "headline": "Corda de saltar",
        "description": "Corda de saltar amb mànecs ergonòmics. Perfecta per a cardio, escalfament o entrenament a qualsevol lloc. Lleugera i ajustable. Posa el cor a to.",
    },
    {
        "code": "l1l116",
        "headline": "Manuelles d'1 kg (parell)",
        "description": "Parell de manuelles d'1 kg recobertes de neoprè. Agafada suau i antilliscant. Ideals per tonificar, pilates o rehabilitació. Còmodes per començar.",
    },
    {
        "code": "l1l117",
        "headline": "Estoreta de ioga de suro",
        "description": "Estoreta de ioga de suro natural antilliscant amb línies d'alineació. Inclou funda de transport. Bona adherència fins i tot amb suor. Per a ioga, pilates o estiraments.",
    },
    {
        "code": "l1l118",
        "headline": "Set de manuelles ajustables",
        "description": "Set de manuelles i kettlebell ajustables amb discos i barres. Adapta el pes a cada exercici. Tot en un per entrenar força a casa. Estalvia espai.",
    },
    {
        "code": "l1l119",
        "headline": "Set d'estris de cuina negre",
        "description": "Set de 4 estris de niló: espàtula, cullerot, batedor i cullera ranurada. Aptes per a tota mena de paelles i olles.",
    },
    {
        "code": "l1l120",
        "headline": "Set d'estris de cuina d'acer",
        "description": "Set de 6 estris d'acer inoxidable: escumadora, aixafador, batedor, cullerot, espàtula i forquilla. Complet i resistent.",
    },
    {
        "code": "l1l121",
        "headline": "Ganivet Santoku Wüsthof",
        "description": "Ganivet santoku professional Wüsthof Classic 17 cm. Tall precís per a verdures, carn i peix. En molt bon estat.",
    },
    {
        "code": "l1l122",
        "headline": "Set d'olles antiadherents",
        "description": "Set de dues olles antiadherents amb nanses ergonòmiques. Perfectes per cuinar sense que s'hi enganxi res. Mides gran i mitjana.",
    },
    {
        "code": "l1l123",
        "headline": "Cassó d'acer inoxidable",
        "description": "Cassó d'acer inoxidable de qualitat professional. Ideal per a salses i cremes. Fàcil de netejar i molt durador.",
    },
    {
        "code": "l0l001",
        "headline": "Zebra, Rosie i Jade – el meu trio de terracota busca casa!",
    },
    {
        "code": "l0l002",
        "headline": "Sa Majestat l'Echeveria – corona rosa, cries gratis!",
    },
    {
        "code": "l0l003",
        "headline": "Capvespre en un test – cria préssec-lila per adoptar!",
    },
    {
        "code": "l0l004",
        "headline": "La boleta peluda – fulles vellutades, cria gratis!",
    },
    {
        "code": "l0l005",
        "headline": "De les meves mans a les teves – tria la teva cria!",
    },
    {
        "code": "l0l006",
        "headline": "El meu miniprat – cinc suculentes germanes sota un sostre!",
    },
    {
        "code": "l0l007",
        "headline": "Moltes cries i pocs testos – vine a rescatar-ne una!",
    },
    {
        "code": "La1a00",
        "headline": "Algú té una escaleta? La prestatgeria alta guanya! 🪜",
    },
    {
        "code": "1u1u01",
        "headline": "Ribot de fuster tipus Stanley",
        "description": "Un clàssic entre els clàssics: cos metàl·lic robust, mànec ben conservat i aquell encenall fi sortint de la fulla que demostra un ajust perfecte. Ideal per a qui busca precisió sense dependre de l'electricitat.",
    },
    {
        "code": "1u1u02",
        "headline": "Peu de rei i compàs de precisió",
        "description": "Dos clàssics per mesurar amb exactitud: el calibre metàl·lic manté les escales llegibles i el mecanisme llisca sense entrebancs, mentre que el compàs conserva la punta ferma per traçar cercles sense desviar-se.",
    },
    {
        "code": "1u1u03",
        "headline": "Ribot elèctric en plena acció",
        "description": "Se'l veu treballant sobre una post de pi, deixant aquell encenall fi que delata un tall ben esmolat. Les mans protegides amb guants confirmen que qui el fa servir sap què fa i cuida la seva seguretat.",
    },
    {
        "code": "1u1u04",
        "headline": "Set tradicional de talla en fusta",
        "description": "Una brotxa, una navalla de tallar, un martell amb el mànec desgastat per l'ús i una garlopa petita de fusta massissa formen aquest conjunt amb molt d'ofici al darrere. Cada peça té la seva funció clara.",
    },
    {
        "code": "1u1u05",
        "headline": "Mini radial amb set de puntes i raspalls",
        "description": "Una eina rotativa compacta acompanyada d'un bon assortiment de puntes abrasives i raspalls metàl·lics, ideal per polir, escatar o donar els últims retocs a peces petites. S'hi veu poc desgast.",
    },
    {
        "code": "1u1u06",
        "headline": "Serra d'englet elèctrica per a motllures i sòcols",
        "description": "Aquesta serra d'englet es fa servir clarament per a feines d'acabat: aquí hi ha la motllura blanca acabada de tallar com a prova. El disc llueix en bon estat i la base es veu estable per a talls nets i sense vibracions.",
    },
    {
        "code": "1u1u07",
        "headline": "Enformadors i maça de fusta per a fusteria",
        "description": "Dos enformadors amb mànec de fusta i tall ben cuidat, al costat d'una maça massissa perfecta per a cops precisos sense malmetre el mànec. Al fons s'entreveu un petit ribot de fusta que completa el set.",
    },
    {
        "code": "1u1u08",
        "headline": "Equip de bufadors de vidre en plena feina",
        "description": "Aquí veiem l'ofici en acció: la canya de bufar sosté una peça de vidre incandescent acabada de treure del forn, mentre l'artesà la treballa amb calma i control. El davantal de cuir diu la resta.",
    },
    {
        "code": "1u1u09",
        "headline": "Kit d'electricista: crimpadora, alicates i grapadora",
        "description": "Tot el que cal per a un cablejat net: crimpadores de colors, alicates de tall, un comprovador de tensió i fins i tot una grapadora manual per fixar cables. Les ulleres de protecció hi van incloses.",
    },
    {
        "code": "1u1u10",
        "headline": "Enclusa de farga amb martell de ferrer",
        "description": "Un conjunt clàssic de forja: l'enclusa conserva la forma i la solidesa malgrat el pas dels anys, i la maça de mànec de fusta es veu forta i ben equilibrada. S'hi nota l'ús real d'un taller.",
    },
    {
        "code": "1u1u11",
        "headline": "Set de joieria per treballar metalls fins",
        "description": "Una mini enclusa de joier acompanyada d'alicates, bufador i una peça a mig fer mostren el detall mil·limètric que exigeix aquest ofici. Tot l'instrumental es veu cuidat i a punt per continuar.",
    },
    {
        "code": "1u1u12",
        "headline": "Maletí de carraca i claus de tub complet",
        "description": "Un joc de claus de tub i carraca amb força recorregut, es nota pel color desgastat del maletí, però totes les peces són al seu lloc i a punt per collar qualsevol cargol.",
    },
    {
        "code": "1u1u13",
        "headline": "Serra d'englet amb xerrac de suport",
        "description": "Aquesta serra d'englet ha vist força feina, i les serradures acumulades ho confirmen, però el disc i l'estructura es mantenen ferms per continuar fent talls en angle amb precisió.",
    },
    {
        "code": "1u1u14",
        "headline": "Kit de soldadura amb careta i elèctrodes",
        "description": "Careta protectora, guant resistent a la calor i varetes d'elèctrode a punt per espurnejar: tot l'essencial per soldar sense ensurts. L'equip es veu complet i en condicions de continuar fent bones soldadures.",
    },
    {
        "code": "1u1u15",
        "headline": "Trio de xerracs de mà multiús",
        "description": "Tres xerracs amb mànecs de colors i dents ben definides, cadascun pensat per a un tipus de tall diferent. Es conserven esmolats i sense rovell, a punt per entrar a qualsevol caixa d'eines.",
    },
    {
        "code": "1u1u16",
        "headline": "Serra d'englet groga amb motllures tallades",
        "description": "Amb diverses peces de fusta ja tallades al costat, aquesta serra d'englet demostra que ha estat a ple rendiment. El groc desgastat i algunes marques d'ús no li treuen mèrit: és de fiar.",
    },
    {
        "code": "1u1u17",
        "headline": "Martell perforador amb broques i punters SDS",
        "description": "Un martell perforador robust acompanyat de broques de gruixos diferents, una escarpra plana i fins i tot els llapis de fuster de tota la vida. Les ulleres de protecció al costat són un bon recordatori.",
    },
    {
        "code": "1u1u18",
        "headline": "Trepant cargolador a bateria",
        "description": "Un trepant compacte i lleuger, amb la bateria inclosa i a punt per fer servir. S'hi veu una mica de pols de feina recent a la superfície, senyal que ha estat en plena feina i no criant pols en un calaix.",
    },
    {
        "code": "1u1u19",
        "headline": "Kit bàsic: martell, cinta mètrica i alicates",
        "description": "El combo essencial per a qualsevol reparació a casa: un martell de mànec blau, una cinta mètrica taronja ben visible, uns alicates multiús i claus de sobres. Senzill, pràctic i sense complicacions.",
    },
    {
        "code": "1u1u20",
        "headline": "Escala professional d'alumini",
        "description": "Escala de treball d'alumini en excel·lent estat, resistent i versàtil. Estructura robusta, esglaons segurs i estables.",
    },
    {
        "code": "1u1u21",
        "headline": "Conjunt de brotxes i pinzells",
        "description": "Conjunt complet de 6 brotxes i pinzells de pintura amb mànecs de fusta natural (grocs i blancs). Varietat de mides i tipus per a treballs de precisió i de cobertura.",
    },
    {
        "code": "L3L301",
        "headline": "Batedora amassadora vermella",
        "description": "Batedora amassadora de color vermell, amb un disseny modern i elegant. Perfecta per preparar tota mena de masses i postres. Bol d'acer inoxidable.",
    },
    {
        "code": "L3L302",
        "headline": "Bicicleta d'aprenentatge per a nens",
        "description": "Bicicleta d'aprenentatge per a nens, ideal per iniciar-se en el món de les dues rodes.",
    },
    {
        "code": "L3L303",
        "headline": "Altaveu amplificat Fenton FT212LED",
        "description": "Altaveu amplificat Fenton FT212LED amb una potència de 1400 W. Té il·luminació LED integrada que canvia de color. Bluetooth, USB i dos micròfons sense fil. En perfecte estat.",
    },
    {
        "code": "L3L304",
        "headline": "Raspberry Pi 5 amb Recalbox a punt",
        "description": "Raspberry Pi 5 de 2 GB completa, amb ventilador integrat, cable HDMI, cable d'alimentació i microSD de 64 GB amb Recalbox a punt per fer servir. Totalment nova.",
    },
    {
        "code": "L3L305",
        "headline": "Lot de set trencaclosques de 1000 peces",
        "description": "Lot de set trencaclosques de la marca That's Life, cadascun amb 1000 peces. Ideals per passar l'estona. Tots complets i en perfecte estat.",
    },
    {
        "code": "L3L306",
        "headline": "Televisor JVC AV14BM8EPS",
        "description": "Televisor JVC model AV14BM8EPS de color platejat. Funciona com a monitor a través de l'entrada frontal. Sense comandament.",
    },
    {
        "code": "L3L307",
        "headline": "Molinet de cafè manual",
        "description": "Molinet de cafè manual, com a decoració o per restaurar. Funciona perfectament.",
    },
    {
        "code": "L3L308",
        "headline": "Paella d'acer polit de 42 cm",
        "description": "Paella molt gran per fer arròs, d'acer polit. 42 cm de diàmetre. Per a 10 persones com a mínim.",
    },
    {
        "code": "L3L309",
        "headline": "Cafetera Nespresso Krups negra",
        "description": "Cafetera Nespresso Krups de color negre. Dissenyada per preparar cafès deliciosos.",
    },
    {
        "code": "L3L310",
        "headline": "Microones Taurus amb grill",
        "description": "Microones Taurus de color blanc amb funció grill. Ideal per escalfar i cuinar. Es troba en molt bon estat, net i a punt per fer servir.",
    },
    {
        "code": "L3L311",
        "headline": "Nevera portàtil per a platja i pícnic",
        "description": "Nevera portàtil amb tapa verda i nansa grisa, ideal per portar begudes i aliments frescos a la platja o de pícnic. El disseny és pràctic i fàcil de transportar.",
    },
    {
        "code": "1u1uRa",
        "headline": "El banc de treball gran",
        "description": "El banc de roure massís, amb el cargol de banc i la bona llum. Reserva'l per a un dia de feina de debò — petita quota de manteniment per a fulles i cola. Es queda al taller.",
    },
    {
        "code": "1u1uRb",
        "headline": "El racó de reunions",
        "description": "Taula, sis cadires i una pantalla per a una reunió petita o una classe. Reservar-lo és gratis, fins a tres dies. Deixa'l com el vas trobar, si us plau.",
    },
    {
        "code": "N3t001",
        "headline": "Trepant sense cable amb joc de broques",
        "description": "Un trepant lleuger amb el seu carregador i un estoig de broques per a fusta, paret i metall. Va bé per a prestatges i barres de cortina.",
    },
    {
        "code": "N3t002",
        "headline": "Vaporeta per a terres i vidres",
        "description": "Vaporeta amb les tres boquilles: terres, vidres i racons. S'omple amb aigua de l'aixeta i es deixa escalfar cinc minuts.",
    },
    {
        "code": "N3t003",
        "headline": "Talla-sebs de gasolina",
        "description": "Un talla-sebs de 60 cm, molt fet servir i encara esmolat. Es presta amb ulleres i guants; el primer dipòsit de combustible el posem nosaltres.",
    },
    {
        "code": "N3t004",
        "headline": "Olla a pressió de 8 litres",
        "description": "Una olla a pressió de 8 litres amb junta de recanvi. Va bé per a llegums, guisats i el dinar gran de família.",
    },
    {
        "code": "N3t005",
        "headline": "Mànega de jardí amb pistoles",
        "description": "Vint metres de mànega amb pistola de reg i tres connectors. Si us plau, buida-la abans de tornar-la.",
    },
    {
        "code": "N3t006",
        "headline": "Batedora de peu amb ganxo de pastar",
        "description": "Una batedora de peu amb vareta, pala i ganxo de pastar. Pa, pastissos i merengues sense mal de braços.",
    },
    {
        "code": "N3t007",
        "headline": "Escala plegable de 3 metres",
        "description": "Una escala d'alumini de tres metres que es plega sobre ella mateixa. Tan lleugera que la porta una sola persona.",
    },
]

FAQS = [
    {
        "thing_code": "La1a01",
        "question": "Puc recollir-ho a final de mes?",
        "answer": "És clar que sí, maco!",
    },
    {
        "thing_code": "La1a02",
        "question": "Puc recollir-ho a final de mes?",
        "answer": "És clar que sí, maco!",
    },
    {
        "thing_code": "La1a03",
        "question": "Puc recollir-ho a final de mes?",
        "answer": "És clar que sí, maco!",
    },
    {
        "thing_code": "La1a04",
        "question": "Puc recollir-ho a final de mes?",
        "answer": "És clar que sí, maco!",
    },
    {
        "thing_code": "La1a05",
        "question": "Puc recollir-ho a final de mes?",
        "answer": "És clar que sí, maco!",
    },
]

# The pickup points of the demo network: the hours (plain text, follows --lang) and the
# conditions each point writes (localized like every owner text).
NETWORK_POINTS = [
    {
        "code": "N3tP01",
        "about": "Som una petita cooperativa de veïnes i veïns. Guardem les eines i els jocs de taula del carrer i els prestem els dimarts i els dijous.\n\nRetorna el que t'emportis **net** i avisa'ns si alguna cosa es trenca: passa.",
        "hours_note": "Dimarts i dijous de 18 a 20 h",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
    {
        "code": "N3tP02",
        "about": "L'associació del Passatge dels Gats Sords, fundada per gent que mai no es va posar d'acord en un nom.\n\nPrestem des del soterrani, els dissabtes al matí, i sempre hi ha temps per xerrar amb un cafè.",
        "hours_note": "Dissabtes de 10 a 13 h",
        "deposit_policy": "20 € de fiança per cosa, que es lliuren en recollir i es retornen tan bon punt torna neta.",
        "request_info": "Porta el carnet de soci. Només obrim els dissabtes; si no pots venir, demana a un veí que la reculli per tu.",
        "email_note": "Truca dues vegades al timbre: som al soterrani, baixant els esglaons de l'esquerra.",
    },
    {
        "code": "N3tP03",
        "about": "Presto des del meu racó de la plaça, a les tardes entre setmana. Escriu-me i quedem.",
        "hours_note": "Tardes entre setmana, per acord",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
    {
        "code": "1u1uP1",
        "about": "Un grup de veïnes i veïns del replà. Som qui mantenim aquesta biblioteca en ordre i responem les teves preguntes.",
        "hours_note": "",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
]
