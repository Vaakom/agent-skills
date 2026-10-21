# Changelog

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
