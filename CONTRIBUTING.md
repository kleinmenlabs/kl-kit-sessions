# Contributing to KL Kit Sessions

Thanks for helping. This kit stays small on purpose: three plain files, a few hooks, no servers and no dependencies beyond Python. Contributions that keep it that way are the easiest to accept.

## Report a bug
Open an issue with the **Bug report** form. Please include:
- Your agent (Claude Code, Codex, Cursor…) and your OS.
- Which hook or file is involved.
- What you did, what you expected and what happened.
- The output of `python3 tests/test_hooks.py` (use `python` on Windows).

**Never paste API keys, tokens or private transcripts.** Trim any log to the lines that matter.

## Suggest an improvement
Open an issue with the **Feature request** form. Tell us the problem first, then your idea. Ideas that add servers, paid services or new dependencies will probably be declined.

## Send a pull request
1. Open an issue first for anything bigger than a typo, so we can agree on the approach.
2. Keep each pull request to one change.
3. Hooks must fail silently: if anything goes wrong, they do nothing and never block by mistake.
4. Hooks only read the local transcript. They must never send data anywhere.
5. Add or update a case in `tests/test_hooks.py` and make sure every test passes.
6. If you change behavior, update both `README.md` and `README.es.md`.
7. Rules and templates are written in English, short and plain.

By contributing, you agree that your work is released under the [MIT License](LICENSE).

---

## Resumen en español
- **¿Encontró una falla?** Abra un *issue* con el formulario **Bug report**: diga qué agente y sistema usa, qué hook o archivo falla, qué hizo, qué esperaba y qué pasó, y pegue el resultado de `python tests/test_hooks.py`. Nunca pegue claves ni conversaciones privadas.
- **¿Tiene una idea?** Use el formulario **Feature request**: primero el problema, después la idea. Lo que agregue servidores, pagos o dependencias nuevas casi seguro no entra.
- **¿Quiere mandar cambios?** Abra primero un *issue*, un cambio por *pull request*, los hooks fallan en silencio y no mandan datos a ninguna parte, las pruebas deben pasar y, si cambia el comportamiento, actualice los dos README. Todo queda bajo licencia MIT.

— Kleinmen Labs
