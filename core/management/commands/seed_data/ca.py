"""
Catalan demo-data text. Merged onto the structural skeleton in common.py by
`seed_demo.load_seed_data`. Collection/thing text is always seeded in every
language at once (localized {lang: text} maps — O6); `--lang=ca` selects this
file for the NON-localizable rest: user bios, FAQs and wish responses.

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
        "headline": "La resistència és fútil! La Lele i el seu swap de circuits.",
        "about": "## El taller de la Lele ⚡\n\nManetes de l'**electrònica** i caçadora de components. El meu coliving funciona amb jumpers i Arduinos a mig fer. Et sobra un Nano o un sensor perdut? Posa'l al tauler i proposa un swap. *La resistència és fútil!*",
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
        "about": "## L'espurna de la comunitat ✨\n\nConec tothom i m'apunto a tot. Guardià de la **Prestatgeria Fantasma** — foto, compartir i veure-ho desaparèixer. Si passa alguna cosa, *ja hi soc*.",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "headline": "La Lala se'n va de sabàtic: tot es ven per deu peles!",
        "description": "Tres regles, company: només efectiu, ho reculls tu, data límit el 25. Queda res? Directe a l'orfenat del barri!",
    },
    {
        "code": "l0l0C1",
        "headline": "El saló verd d'en Lolo – emporta't una suculenta gratis!",
        "description": "Passa a conèixer el meu esquadró suculent – echeveries, jades, sèdums – i et regalo un esqueix. Guia fàcil de cures inclosa. Única regla: posa-li nom a la teva nova amiga verda!",
    },
    {
        "code": "l1l1C1",
        "headline": "Préstecs de la Lili – hora de compartir les coses!",
        "description": "Necessites trepant, vaporeta, escala sòlida, bàscula d'equipatge o un mega kit de magdalenes? La biblioteca de préstecs de la Lili t'ho cobreix – tot a un cost simbòlic!",
    },
    {
        "code": "L3L3C1",
        "headline": "Swap de circuits de la Lele – la resistència és fútil!",
        "description": "El coliving de la Lele funciona amb jumpers i Arduinos a mig fer. Tens un Nano agafant pols? Un sensor que no era teu? Posa'l al tauler, tria el que t'agradi, proposa un swap. Només components — sense diners ni curtcircuits.",
    },
    {
        "code": "1u1uC1",
        "headline": "Prestatgeria fantasma d'en Lulu – aguaita amb els trastos!",
        "description": "Veus alguna cosa agafant pols? Fes-li una foto i puja-la a la prestatgeria fantasma d'en Lulu – sense embolics, sense preus, només un feed de descarts del coliving. Email setmanal amb les novetats! Però afanya't, les coses desapareixen ràpid!",
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
        "code": "1u1u01",
        "headline": "Fondue oblidada",
        "description": "Fonedora de formatge del 98 per a sis! Amb forquilles i pilot inclosos. Agafa-la abans que torni a desaparèixer!",
    },
    {
        "code": "1u1u02",
        "headline": "Maletes vintage apilades",
        "description": "Tres belleses de cuir, fregades menors! Perfectes per a escapades de cap de setmana o emmagatzematge chic. Demana-les abans que desapareguin!",
    },
    {
        "code": "1u1u03",
        "headline": "Bicicleta estàtica bestial",
        "description": "Spinner silenciós amb 8 nivells de resistència! Cardio sense culpa postconfinament. Se'n va en un sospir – força al pedal!",
    },
    {
        "code": "1u1u04",
        "headline": "Testos de ceràmica",
        "description": "Trio de terracota fet a mà, platet inclòs! Reviu les teves suculentes tristes. Estrella del resum setmanal – afanya't!",
    },
    {
        "code": "1u1u05",
        "headline": "Festí de jocs de taula",
        "description": "Monopoly, Cluedo i Pictionary complets! Clàssics del coliving per a nits plujoses. Per ordre d'arribada – volen!",
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
        "code": "L3L301",
        "headline": "Grove Shield per a Arduino Nano v1.1 (Seeed Studio)",
    },
    {
        "code": "L3L302",
        "headline": "Grove - Sensor de pols làser PM2.5 (HM3301)",
    },
    {
        "code": "L3L303",
        "headline": "MB102 Mòdul d'alimentació per a protoboard (HW-131)",
    },
    {
        "code": "L3L304",
        "headline": "Adaptador de terminals per a Arduino Nano",
    },
    {
        "code": "L3L305",
        "headline": "Arduino Nano 33 BLE",
    },
    {
        "code": "L3L306",
        "headline": "CCS811 Sensor de qualitat de l'aire interior",
    },
    {
        "code": "L3L307",
        "headline": "Grove: temperatura i humitat, aigua, so, UV, aire",
    },
    {
        "code": "L3L308",
        "headline": "DFRobot Sensor UV analògic V2 (Gravity)",
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

WISH_RESPONSES = [
    {
        "wish_code": "La1a00",
        "message": "Al traster del costat de l'aparcabicis hi ha una escaleta plegable. Demana-li la clau a en Lolo!",
    },
]
