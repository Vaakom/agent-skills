# Changelog

## 2.1.3 - 2026-10-27

- Validation: 67 portable synthetic skill tests and 11 synthetic recorder integration tests passed; static skill audit passed. No live capture, real speech recognition, meeting UI or notification delivery was tested.

- Reconcile current behavior with portable public instructions; preserve machine setup and operational history in ignored local files.
- Keep bundled GigaAM setup guidance and update the workflow to name the bundled worker.
- Restore configuration diagnostics and include transcript-link checks in the synthetic suite.

## 2.1.2 - 2026-10-25

- Require reviewing the workflow on every skill change and updating affected steps and tools.

## 2.1.1 - 2026-10-25

- Add a compact Mermaid workflow with tools and explicit processing/provider routing.

## 2.1.0 - 2026-10-23

- Stop on bound meeting-window closure or whole-browser closure; other meeting signals remain advisory.
- Preserve audio before the persistent completion dialog; retain stop/advisory evidence.
- Missing journals and monitor failures no longer block requested audio capture.
- Add stable transcript anchors and minutes timestamp links, preserving backups and source-hash checks.

## 1.12.2 - 2026-10-22

- Discover default speaker journals from explicit DION_JOURNALS_ROOT / DION_HELPER_RUNTIME or external application data rather than the obsolete in-vault runtime. Explicit journal_root remains authoritative.

## 1.12.1 - 2026-10-22

- Move the maintained GigaAM worker and model loader into this skill; default processing no longer needs a products directory or an absolute worker path.
- Include optional dependency requirements, explicit model setup and a configurable offline synthetic worker check. Keep environments, downloads and model weights external.
- Remove obsolete comparison experiments from the local products tree. Explicit custom-worker overrides remain supported; existing speech/model choices are unchanged.
- Validation: 58 synthetic tests passed; the bundled worker decoded generated silence and strictly loaded hash-checked GigaAM weights offline. No meeting was recorded or transcribed.

## 1.12.0 - 2026-10-21

- Use one working source tree for development and publication; keep machine configuration and local operational history outside Git.
- Replace contradictory machine paths in shared instructions with configuration and an optional ignored local note.
- Bundle the maintained local-minutes implementation; keep compatibility entrypoints for the existing local product.
- Configure the journal root and support DION_SECRETARY_CONFIG for isolated checks and external configuration.
- Add installation examples and portable synthetic checks. Live recording and configured GigaAM processing require separate environment verification.

Earlier local history is retained in the external preparation backup; it is not a public release history.
