# claude-skills

> **Agent: if you were asked to "open this repository and do what the README says", follow
> [`SETUP.md`](SETUP.md) now, step by step, for the project you are working in.**

Skill condivise per tutti i progetti di stichlola: quello che gli agenti hanno imparato lavorando su
QuestBoard, Jak Enhanced e gli altri progetti, scritto in modo che qualsiasi agente, in qualsiasi progetto,
lo usi da solo quando serve.

> **Agent, every session and every sub-agent:** before starting work, read **all the general skills**
> below (whole `SKILL.md`), then skim the names/descriptions of the topic skills and open the ones that
> fit. When you learn something reusable, or notice a lesson that is missing here, add it to the right
> skill (or a new one), commit **and push** this repository right away.

## Skill generali (per ogni progetto: gli agenti le leggono sempre tutte)

| Skill | Cosa contiene |
|---|---|
| `multi-agent-orchestration` | **risparmio token** (effort basso per i compiti meccanici, pochi screenshot ridotti, rapporti brevi a formato fisso, letture parziali, pochi agenti paralleli), forma dei workflow (ricerca in parallelo â†’ un solo implementatore â†’ verifica indipendente â†’ correzione), giri su una lista di cose da fare (un punto esce solo quando Ã¨ fatto, corsia a parte per i lavori tecnici grandi), riprendere un workflow senza rifare il lavoro (stessi args), fermare agenti senza lasciare modifiche di debug, memoria impegnata (commit) oltre alla RAM, build di un worktree che l'utente sta provando, release su linea lenta, pulizia del disco. |
| `planner-builder` | **Fable che pianifica e rivede + Opus che scrive il codice** (orchestrator-workers + routing dei modelli per costo): ruoli, modello/impegno di default (tutti medio, si alza/abbassa per difficoltÃ ), forma del Workflow con `model`/`effort` per agente, escalation invece di ripartire, come richiamarlo (`/studio:planner-builder <obiettivo>` o "usa planner-builder"). |
| `cloud-agent-workflow` | regole di lavoro nelle sessioni lunghe e cloud: git sicuro (worktree, commit firmati, main allineato), niente `pkill`, lavori lunghi in background, Playwright senza GPU, controlli prima di dire "fatto", un commit per voce anche con piu' voci nello stesso file. |
| `mesh-hygiene` | **in ogni lavoro di modellazione 3D** (Blender, scan, modelli Tripo, booleane, remesh, sculpt, tagli, export STL/OBJ/FBX/GLB): prima di consegnare o esportare una mesh controllare e pulire la geometria sporca e riportare i numeri: vertici e spigoli doppi, triangoli degeneri a spessore zero, spigoli non-manifold e buchi, vertici a farfalla, normali invertite, frammenti staccati, volume prima/dopo. Differenze fra mesh da stampa e da gioco. Script `scripts/mesh_clean.py` per Blender in background. |

## Skill per argomento

| Skill | Quando la usa l'agente |
|---|---|
| `tripo-3d-assets` | fare modelli 3D con Tripo: facce decise in partenza, fogli di pezzi tagliati in Blender, P1 + texture da un'immagine, concept prima dei personaggi, animare creature non umane da video generati (due telecamere in un'immagine, esame prima di pagare), costi, errori giÃ  visti. Con un piccolo client (`scripts/tripo_client.py`). |
| `threejs-performance` | scene three.js lente o brutte: lag dei primi secondi, shader ricompilati, qualitÃ  adattiva, instancing, ombre che spariscono, misure prima/dopo. |
| `blender-wearable-hollowing` | rendere cavo e indossabile un modello 3D in Blender (teste mascotte, elmi, maschere): scavo con Geometry Nodes SDF, apertura sotto senza cambiare il profilo, capelli allungati, occhi rimovibili con sedi magnete in mm reali, verifiche numeriche, bake per lo sculpt a mano, render per il cliente, divisione in pezzi con linguette magnetiche, scala adattata a un accessorio vero (occhiali: tasche cieche per le stanghette con gioco), sedi magnete rifatte a misura reale dopo la scala e perpendicolari al giunto, tabella magneti (10Ã—3, 5Ã—2), verifica di ogni sede con profili lungo l'asse, controllo interferenze a pezzi montati, prova con una testa scansionata e scavo locale per fare spazio, booleane Manifold e lavori pesanti in un Blender in background, trappole di MCP for Blender. Con lo script completo (`scripts/wearable_head_build.py`) e quello di verifica (`scripts/seat_check.py`). |
| `blender-engraved-dice` | dadi personalizzati con parole incise da stampare (D8 verificato, metodo valido per D4-D20): dado pulito ricostruito da un STL con supporti, bevel, una scritta per faccia centrata e adattata al triangolo, incisione in SDF in meno di un secondo invece dei booleani che bloccano Blender, oppure i tagli lasciati all'utente, maschere per dipingere le incisioni, orientamento e supporti per la resina. Con lo script (`scripts/engrave_die.py`). |
| `opengoal-jak-extraction` | estrarre dal disco di Jak (1/2/3) con OpenGOAL quello che serve a un remake: cosa perde il ripper glb (canale align, chiavi a 15 fps, terreno hfrag), dune e sabbia Wang dal `.fr3`, effetti sonori dalle banche SBK, la musica in streaming di `VAGWAD.INT` (con il decoder `scripts/vagwad_music.py`), unitÃ  e assi GOAL, piÃ¹ istanze del gioco in parallelo per i test (porte, config, capacitÃ ), un release gate a scenari (righe headless in parallelo, fine anticipata, confronto screenshot con la baseline) e gli hook di test in GOAL (handle nei globali a 32 bit, `~A` con le virgolette), mosse fatte a mano per i personaggi giocabili (bone aiming in GOAL; giunti mescolati con slerp, gonne sulle cosce smorzate verso i fianchi; braccia di un rig legato in un'altra posa: correzione della direzione di bind, pugni chiusi, foto prima/dopo congelando il fotogramma; mosse d'attacco nuove da clip di movimento generate: misurare le clip prima di usarle, tabelle di pose indipendenti dal rig, tempi stilizzati, dissolvenza dalla posa disegnata, miscele a slerp invece che per righe, watcher che misura le animazioni), crash senza errore GOAL letto dal minidump (0xC0000094 = `go` a uno stato non definito, registri r13/r15, stati a zero dal REPL), caricatori sull'HUD e log leggibili (niente debug nel file, ripetizioni riassunte, goalc senza righe di progresso; verifica: regex degli script provate su un log di base, errori veri forzati; ultime righe di debug scritte su un die o un crash; build GOAL di un worktree con `--user-auto`), effetti luminosi visibili di giorno (copie prima/dopo gli sprite, solo sorgenti compatte), ombre (distanza dal caster in metri, niente ombre da draw senza z, direzione della luce quantizzata); prove senza audio (`JAK_ENHANCED_MUTE`); un personaggio nuovo sullo scheletro di Jak (modello scambiato in Merc2, tutti gli effetti accesi, IBM come posa di bind, scala dei giunti non ereditata, worktree e `dev_bin -From`). |
| `unreal-engine-pipeline` | Unreal Engine 5 da codice e Python: import headless, master material in Python, limiti di Nanite, istanze grigie, costi delle ombre virtuali, glow che diventano bianchi, crash da puntatori UObject, audio, misure fps, commandlet affidabili su Windows. |
| `blender-world-building` | costruire e modificare un mondo di gioco in Blender e portarlo nel motore: livelli spostati con un file di layout, terreno che chiude una cittÃ  tra le montagne e si unisce senza giunture, pennelli Vertex Paint per sabbia/roccia/prato, pennelli Weight Paint che spargono erba, alberi, rocce e case, cittÃ  procedurali, tunnel, scritte, esportazione come istanze, materiale triplanare in UE, rilevatore automatico di buchi; fondale dipinto per un render (foschia nel materiale, terreno polare, CAM_BASE + CAM_SHOT, tremolio a mano estratto da un video di riferimento). |
| `video-mocap-retarget` | motion capture da un video sul PC (NVIDIA GEM-X su Windows: installazione, rilevatore sostituito, uscite SOMA) e retarget su un rig in Blender headless: clip registrate dallo schermo (taglio, fotogrammi doppi), soggetto seduto o coperto (allineare lo yaw alla camera, mai normalizzare il bacino), filtro a fase zero con numeri di accettazione, contatti analitici (davanzale, volante, grembo, bocca) cotti in FK, dita a mano, camera ricostruita da quella del mocap; faccia: bocca aperta lungo le labbra dipinte di una mesh AI, palpebre nascoste a riposo, 52 shape key ARKit da pose di ossa, cattura MediaPipe di una faccia piccola (tracking a ritaglio, pulizia, controllo sinistra/destra), azioni a channelbag in Blender 5. |
| `game-art-review-loop` | migliorare una zona di gioco a giri con agenti che giudicano: foto dal gioco in un solo avvio, un art director AAA che dÃ  i voti, un QA che elenca i difetti con le coordinate, un ingegnere che legge il codice, localizzatore dei difetti dalla camera del gioco, correzione automatica, confronto tra giri, macerie fatte dai muri tagliati e assestate con la fisica, trappole viste (culling, UV, colori di vertice, collisioni che spostano la camera). |
| `retro-renderer-modern-post` | effetti grafici moderni nel renderer PC di un gioco vecchio (OpenGOAL), materiali di dettaglio tileabili nei shader dei livelli: un passaggio sulla scena prima dell'HUD, posizioni ricostruite dalla profonditÃ , TAA con jitter iniettato negli shader del mondo, nebbia volumetrica, ombre e luce indiretta in screen space, come provare gli effetti legati al sole, cosa lo screen space non puÃ² fare, timer GPU per passaggio, dominanti blu al tramonto, GTAO, cache della mappa d'ombra vicina, costo del frame RGBA16F, veli da incantesimi meteo casuali, correzioni limitate a un livello, uniform scalati per area, virgola decimale nei file di tuning, profilare un composite enorme (skip a runtime, non uscite anticipate), AO/GI temporali a metÃ  campioni, shading a tasso variabile (VRS) sul composite, mappe d'ombra cubiche per i lampioni, lampioni sfocati per colpa di un effetto che ridisegna i bagliori, mezzogiorno piatto e slavato (luce chiave di lato e piÃ¹ bassa, superfici tolte dalla spalla delle alte luci, fattore in un componente libero di un vec4), acqua piÃ¹ chiara del cortile in ombra (ombra del sole e occlusione anche sul riflesso e sul corpo dell'acqua), A/B dell'acqua con meteo sereno, orologio fermo e fotogrammi mediati, un fotogramma nero a ogni cambio di risoluzione (texture ricreate che sganciano l'unitÃ  0 del composite) e la sonda che lo trova dal log, schizzi sull'acqua (sprite rimessi per copertura, la mesh di increspatura del warp trattata come acqua, anello del tuffo), bordi chiari a poligono attorno alle chiazze di roccia piatte sulla sabbia (peso "roccia sulla sabbia" nello shader del livello: altezza sul terreno, verso l'alto, luce come le dune).; schiuma attenuata al tramonto ma luci colorate sull'acqua a guadagno 1, spari nei test senza pad (prova "shoot" riarmata dal REPL); esplosioni di giorno senza macchia bianca sulla sabbia, palette serale per zona, interruttori come bit in un vec4, test di un worktree con --proj-path |; camera di photo mode tenuta ferma dal file di tuning (debug.photo/debug.view) per inquadrare ciò che la camera di gioco non raggiunge, vento del meteo da loggare prima di dire "tempesta x3", niente spruzzi da ruote sui veicoli che volano, compilare GOAL in un worktree col suo goalc; pozzanghere nelle conche lette dalla profondità, niente pioggia sui veicoli volanti (per draw), ombre dei fulmini; pop-in al caricamento dei livelli (fade a dither riacceso, ripartenza solo dopo un vero vuoto, fade per scenery e oggetti piazzati)

Le skill sono in inglese (le leggono gli agenti); l'agente risponde comunque nella tua lingua.

## Come metterle in un progetto nuovo

### 1. Sessioni cloud (claude.ai/code, app): una frase all'agente (consigliato)

Le sessioni cloud caricano le skill che stanno **dentro il repository** (`.claude/skills/`). Nella prima
sessione del progetto nuovo scrivi solo:

> Apri `stichlola/claude-skills` e fai quanto scritto nel README.

L'agente segue `SETUP.md`: copia le skill, aggiunge la riga al CLAUDE.md, fa commit e push. La stessa frase
serve anche per **aggiornarle** dopo una modifica qui.

Oppure a mano, da un computer con entrambi i repository:

```bash
git clone https://github.com/stichlola/claude-skills
claude-skills/tools/install-into.sh /percorso/del/progetto
cd /percorso/del/progetto && git add .claude/skills && git commit -m "Shared skills" && git push
```

Per **aggiornarle** (dopo una modifica qui) si rilancia lo stesso comando nel progetto.

### 2. Claude Code sul tuo computer: una volta sola per tutti i progetti

```text
/plugin marketplace add stichlola/claude-skills
/plugin install studio@stichlola
```

Scegli "Install for you (user scope)": da lÃ¬ valgono in ogni progetto aperto sul tuo computer. Se il
repository Ã¨ privato serve che git sul computer abbia accesso a GitHub (`gh auth login`, poi
`gh auth setup-git`). Gli aggiornamenti: `/plugin` â†’ Marketplaces â†’ aggiorna (o attiva l'aggiornamento
automatico).

### 3. Chat di claude.ai (facoltativo)

Comprimi in zip una cartella di skill (es. `plugins/studio/skills/tripo-3d-assets/`, con la cartella stessa
dentro lo zip) e caricala da Customize â†’ Skills â†’ "+" â†’ Upload a skill.

### 4. Una riga nel CLAUDE.md del progetto (facoltativo ma utile)

```markdown
- Skill condivise in `.claude/skills/` (da `stichlola/claude-skills`): a inizio lavoro leggi tutte le skill
  generali (`multi-agent-orchestration`, `cloud-agent-workflow`, `mesh-hygiene`), poi quelle per argomento che servono;
  quando scopri qualcosa di utile per altri progetti, aggiungilo lÃ¬ e fai push.
```

## Come si aggiunge una scoperta

Si modifica la skill giusta in `plugins/studio/skills/<skill>/SKILL.md` (o se ne crea una nuova cartella
con il suo `SKILL.md`: in alto `name` e `description`, che dice **quando** usarla; se vale per ogni
progetto va anche nella tabella delle skill generali), commit e **push subito** qui,
poi `tools/install-into.sh` nei progetti che la usano. Basta chiedere a un agente: "aggiungi questa
scoperta alle skill condivise".

## Struttura

```
.claude-plugin/marketplace.json       il "negozio" stichlola (per /plugin)
plugins/studio/.claude-plugin/plugin.json
plugins/studio/skills/<skill>/SKILL.md   le skill (+ reference/ e scripts/)
tools/install-into.sh                 copia le skill in un progetto
```
