<p align="center"><img src="assets/banner.png" alt="KL Kit Sessions by Kleinmen Labs" width="100%"></p>

# KL Kit Sessions

*[Read in English](README.md)*

Las sesiones de los asistentes de programación con IA olvidan, se comen el cupo y se cortan sin aviso. Este kit lo arregla con tres archivos de texto y ocho frenos pequeños. No necesita servidores ni modelos extra, solo Python.

**Sirve con:** Claude Code, Codex, Cursor y cualquier asistente que lea `AGENTS.md` (las reglas y los archivos). Los frenos son **solo para Claude Code**.

## Novedades
- **v1.5 (21 nov 2026):** **lo que usted escribe después de `/clear` manda.** Si pega un texto o pide una tarea, la sesión hace eso, en vez de sacarle primero una pregunta vieja que quedó pendiente o una lista de opciones (eso solo pasa si dice "siga" o saluda). Después de `/clear` una ventana ya no se trae la conversación de otra: si no está segura de cuál era la suya, no trae ninguna. Cuando una ventana no sabe qué venía haciendo y hay otras trabajando, le muestra una lista numerada de temas para escoger, en vez de preguntarle "¿qué venía haciendo?". Un texto para pegar que nombra un proyecto sin ruta recibe el extracto del STATE.md de ese proyecto, y una pregunta pendiente vuelve con la respuesta que la hizo, no con lo más nuevo del STATE.md. Una tarea escrita en una ventana nueva ya no se desvía. 61 pruebas.
- **v1.4 (19 nov 2026):** las ventanas ya no se traen el trabajo de otras después de estar quietas mucho rato. Freno nuevo `continue_without_clear.py`: "siga" o "hola" en una conversación con historia es lo suyo, no lo último del STATE.md compartido. Después de `/clear`: las opciones que le dieron vuelven al pie de la letra (mismos números), un mensaje que el freno bloqueó cuenta como su respuesta, las conversaciones resumidas conservan su tarea, el aviso de límite de uso ya no se toma como la última respuesta y, si no se sabe la tarea de la ventana y hay otras trabajando, pregunta en vez de adivinar. Las tildes ya no se dañan en Windows y los frenos respetan `CLAUDE_CONFIG_DIR`. Nuevo: instálelo pidiéndoselo a su asistente. **Arranque más barato:** "¿cómo vamos?" lo contesta el kit mismo desde el STATE.md (0 tokens); después de `/clear` la sesión recibe un extracto corto en vez de leer todo el STATE.md; y un freno de lectura no deja que el asistente lea archivos enteros ni el historial (todo lo que lee se vuelve a mandar en cada paso). 56 pruebas.
- **v1.3 (18 nov 2026):** una **barra** opcional para Claude Code: *"KL Kit Sessions: 426k tokens saved with /clear · this window: 105k · 5 windows: 380k"*. Cuenta lo que el kit le ha ahorrado (cada conversación pesada que usted limpió o que el freno bloqueó cuenta una vez, con su tamaño), cuánto pesa esta ventana ahora y la suma de sus ventanas abiertas. Freno nuevo `tokens_saved.py`, que usan `heavy_session.py` y `remember_window.py`. 31 pruebas.
- **v1.2 (17 nov 2026):** el texto para pegar **ya no puede aprobar cosas por usted.** Solo trae tareas que usted pidió, nunca "el usuario dijo que sí" cuando no lo dijo. Si la última respuesta le dejó una pregunta y usted no la contestó, después de `/clear` la sesión nueva se la vuelve a hacer primero y espera, en vez de hacer la tarea. Si el texto habla de una aprobación, la sesión comprueba que usted sí la dio. 27 pruebas.
- **v1.1 (16 nov 2026):** después de `/clear`, cada ventana vuelve a **su propia** tarea en vez de meterse en el trabajo de otra. "Siga" ahora es el texto que esa ventana le dejó (o su último pedido), encuentra el proyecto real aunque la sesión se haya abierto en otra carpeta, y un freno nuevo, `message_to_window.py`, hace que un pedido llegue a la ventana correcta y a una sola. 23 pruebas.
- **v1.0 (16 nov 2026):** primera versión.

## El problema
- **Cada sesión nueva arranca de cero.** Usted vuelve a explicar el proyecto, o el asistente lee medio repositorio para saber en qué va.
- **Las sesiones largas salen caras.** Volver a una conversación enorme después de una hora la recarga toda de una vez, y un solo mensaje puede gastar buena parte del cupo de 5 horas.
- **El corte llega sin aviso.** El asistente no ve cuántos tokens lleva, así que la sesión se cae a mitad del trabajo y se pierde lo que solo estaba en el chat.

## La solución
| Pieza | Qué hace |
|---|---|
| `STATE.md` | Una página: Ahora · Hecho · Siguiente · Datos clave. Es **lo único** que lee una sesión nueva. Se reemplaza, nunca se vuelve un diario. |
| `STATE_tracks.md` | Para varias sesiones a la vez en la misma carpeta: una sección por frente. También sirve para las partes de un proyecto y para una carpeta madre con varios proyectos adentro (un frente por proyecto). "¿Cómo vamos?" da una línea por frente, el más reciente primero; "siga" sigue con el frente más reciente y dice cuál. |
| `HISTORY.md` | Una línea por cada cosa terminada. No se lee al arrancar; solo se busca cuando falta un dato viejo. |
| Reglas en `AGENTS.md` (+ un `CLAUDE.md` que las carga) | Leer STATE.md al abrir, anotar **después de cada paso** (no solo al final) y, cuando la sesión pesa, dejar un texto listo para pegar en una sesión nueva. Un solo archivo que leen todos los asistentes. |
| Freno `heavy_session.py` (Claude Code) | Sesión pesada y quieta: bloquea el mensaje antes de mandarlo, sin gastar nada. Pesada y activa: le dice a Claude cuánto pesa, una sola vez, para que guarde y le deje el texto de la sesión nueva. |
| Freno `continue_after_clear.py` (Claude Code) | Después de `/clear`, escriba "siga" (o el nombre del frente) en vez de pegar el texto. "Siga" es la tarea que **esa ventana** venía haciendo: el texto que le dejó en su última respuesta o su último pedido. Encuentra el proyecto en que de verdad trabajaba, aunque la ventana se haya abierto en otra carpeta, y no toca lo que están haciendo las otras ventanas. |
| Freno `remember_window.py` (Claude Code) | Corre en el `/clear` y anota qué conversación tenía esa ventana, para que `continue_after_clear.py` sepa en qué frente iba, aunque otra ventana haya actualizado STATE.md después. |
| Freno `continue_without_clear.py` (Claude Code) | "Siga" o un saludo en una conversación que ya tiene historia es el trabajo de esa conversación, nunca lo último de un STATE.md que comparte con otras ventanas. |
| Freno `how_are_we.py` (Claude Code) | "¿Cómo vamos?" lo contesta el kit desde el STATE.md, una línea por frente. El mensaje no le llega al asistente: 0 tokens. |
| Freno `read_guard.py` (Claude Code) | No deja que el asistente lea un archivo grande entero, lo vuelque con `cat` ni lea el historial: tiene que buscar y leer solo el pedazo que necesita. Usa `state_excerpt.py`, que también sirve después de `/clear`. |
| Freno `message_to_window.py` (Claude Code) | Antes de que una sesión le mande un mensaje a otra ventana con nombre de carpeta (`app-77`, `app-62`…), le muestra qué está haciendo cada ventana abierta, para que el pedido llegue a la correcta. El mismo pedido nunca va a dos ventanas. |
| `tokens_saved.py` (Claude Code) | Cuenta los tokens que el kit le ahorró: cuando `heavy_session.py` bloquea una conversación pesada y quieta o usted le hace `/clear` a una, su tamaño se suma una vez en `~/.claude/hooks/tokens_saved.json`. Es un estimado. |
| Barra `plugin/` (Claude Code, opcional) | Siempre a la vista: tokens ahorrados con `/clear`, lo que pesa esta ventana y la suma de sus ventanas abiertas. Se actualiza cada minuto y después de cada respuesta. |
| Freno `require_state.py` (Claude Code) | Si Claude cambió archivos de un proyecto con STATE.md y no lo actualizó, no lo deja terminar hasta que lo haga. |

Así una sesión nueva arranca con *"Siga con el proyecto. Lea solo el archivo de reglas y STATE.md. Lo primero en 'Siguiente' es: …"*, gasta poco y en un minuto ya sabe en qué va todo.

## Instalación
**Lo más rápido: pídaselo a su asistente.** Abra Claude Code y pegue: `Install the session kit from https://github.com/kleinmenlabs/kl-kit-sessions`. Copia los frenos, las reglas, la habilidad y las plantillas, y junta los frenos con su `settings.json` en vez de reemplazarlo. Los pasos de abajo son la forma manual.

1. **En cada proyecto** (cualquier asistente): copie `templates/` al proyecto y llene `AGENTS.md` y `STATE.md`. El `CLAUDE.md` solo trae `@AGENTS.md`, para que Claude Code lea las mismas reglas. Las reglas del proyecto siempre ganan sobre las globales.
2. **Reglas globales** (opcional, para todos los proyectos), desde `global/AGENTS.md`. Si ya tiene reglas globales, agréguelas al final en vez de reemplazarlas:
   - Claude Code: cópielo a `~/.claude/CLAUDE.md`.
   - Codex: cópielo a `~/.codex/AGENTS.md`.
   - Cursor: péguelo en Settings → Rules → User Rules.

### Solo en Claude Code
3. **Frenos:** copie los `hooks/*.py` a `~/.claude/hooks/` y agregue el bloque `hooks` de `hooks/settings.example.json` a su `~/.claude/settings.json`. En Windows use `python` en vez de `python3` y la ruta completa, por ejemplo `C:/Users/usted/.claude/hooks/heavy_session.py` (no `/c/...`). Si ya tiene un `settings.json`, agregue el bloque; no reemplace el archivo.
4. **Habilidad (opcional):** copie `skills/session-kit` a `~/.claude/skills/session-kit` y deje al lado la carpeta `templates/` (`~/.claude/skills/session-kit/templates`), porque la habilidad arma los archivos desde ahí. Después escriba `/session-kit` en cualquier proyecto y se lo prepara solo.
5. **Barra (opcional):** ejecute `claude plugin marketplace add kleinmenlabs/kl-kit-sessions` y después `claude plugin install kl-kit-sessions-bar@kl-kit-sessions` (o `/plugin` dentro de Claude Code). Sale en las sesiones nuevas. Lee `~/.claude/hooks/` (o `$CLAUDE_CONFIG_DIR/hooks/`), así que instale primero los frenos del paso 3.

Pruebe los frenos con `python3 tests/test_hooks.py` (56 casos, sin tocar sesiones reales) y la barra con `claude plugin test plugin`.

## Ajustes
Arriba en `hooks/heavy_session.py`:
- `HEAVY_TOKENS = 100_000`: desde cuántos tokens la sesión cuenta como pesada.
- `IDLE_MINUTES = 55`: cuánto tiempo quieta antes de bloquear. Va con una caché de 1 hora; bájelo si la suya dura menos.
- `FORCE_WORD = "force"`: empiece el mensaje con esa palabra para saltarse el bloqueo.

Arriba en `hooks/require_state.py`: `MARGIN_MINUTES = 30` y el nombre del archivo, `STATE.md`.

## Cómo colaborar
¿Encontró una falla o tiene una idea? Abra un *issue* con los formularios (puede escribir en español) o lea [CONTRIBUTING.md](CONTRIBUTING.md) antes de mandar un *pull request*.

## Notas
- Los frenos solo leen el registro de la sesión que Claude Code ya guarda en su equipo. No mandan nada a ninguna parte.
- Si un freno falla por cualquier razón, no hace nada: nunca bloquea por error.
- Los archivos están en inglés porque los modelos lo siguen bien y gasta menos tokens. El asistente le sigue respondiendo en su idioma.
- Los frenos leen el registro de sesión de Claude Code. Los otros asistentes guardan sus sesiones de otra forma, así que allá no aplican los frenos; las reglas y los archivos sí.

## Licencia
MIT. Vea [LICENSE](LICENSE).

---
Hecho por **Kleinmen Labs**.
