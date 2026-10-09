# claude-skills

Skill condivise per tutti i progetti di stichlola: quello che gli agenti hanno imparato lavorando su
QuestBoard, scritto in modo che qualsiasi agente, in qualsiasi progetto, lo usi da solo quando serve.

| Skill | Quando la usa l'agente |
|---|---|
| `tripo-3d-assets` | fare modelli 3D con Tripo: facce decise in partenza, fogli di pezzi tagliati in Blender, P1 + texture da un'immagine, concept prima dei personaggi, costi, errori già visti. Con un piccolo client (`scripts/tripo_client.py`). |
| `threejs-performance` | scene three.js lente o brutte: lag dei primi secondi, shader ricompilati, qualità adattiva, instancing, ombre che spariscono, misure prima/dopo. |
| `cloud-agent-workflow` | regole di lavoro nelle sessioni cloud: git sicuro (worktree, commit firmati, main allineato), niente `pkill`, lavori lunghi in background, Playwright senza GPU, controlli prima di dire "fatto". |

Le skill sono in inglese (le leggono gli agenti); l'agente risponde comunque nella tua lingua.

## Come metterle in un progetto nuovo

### 1. Sessioni cloud (claude.ai/code, app): copia nel progetto (consigliato)

Le sessioni cloud caricano le skill che stanno **dentro il repository** (`.claude/skills/`). In una sessione
del progetto nuovo scrivi all'agente:

> Aggiungi alla sessione il repository `stichlola/claude-skills`, poi esegui
> `tools/install-into.sh <cartella del progetto>` e fai commit di `.claude/skills/`.

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

Scegli "Install for you (user scope)": da lì valgono in ogni progetto aperto sul tuo computer. Se il
repository è privato serve che git sul computer abbia accesso a GitHub (`gh auth login`, poi
`gh auth setup-git`). Gli aggiornamenti: `/plugin` → Marketplaces → aggiorna (o attiva l'aggiornamento
automatico).

### 3. Chat di claude.ai (facoltativo)

Comprimi in zip una cartella di skill (es. `plugins/studio/skills/tripo-3d-assets/`, con la cartella stessa
dentro lo zip) e caricala da Customize → Skills → "+" → Upload a skill.

### 4. Una riga nel CLAUDE.md del progetto (facoltativo ma utile)

```markdown
- Skill condivise in `.claude/skills/` (da `stichlola/claude-skills`): usale per Tripo, three.js e il
  flusso di lavoro; quando scopri qualcosa di utile per altri progetti, proponi di aggiungerlo lì.
```

## Come si aggiunge una scoperta

Si modifica la skill giusta in `plugins/studio/skills/<skill>/SKILL.md` (o se ne crea una nuova cartella
con il suo `SKILL.md`: in alto `name` e `description`, che dice **quando** usarla), commit e push qui,
poi `tools/install-into.sh` nei progetti che la usano. Basta chiedere a un agente: "aggiungi questa
scoperta alle skill condivise".

## Struttura

```
.claude-plugin/marketplace.json       il "negozio" stichlola (per /plugin)
plugins/studio/.claude-plugin/plugin.json
plugins/studio/skills/<skill>/SKILL.md   le skill (+ reference/ e scripts/)
tools/install-into.sh                 copia le skill in un progetto
```
