# yappy-devkit Roadmap

## Fase 0 — Fundación
- [x] Estructura del proyecto Python modular
- [x] Sistema de configuración por entorno: `config/env.base` + `config/env.<env>`
- [x] CLI con [Typer](https://typer.tiangolo.com/)
- [x] Clase base `BaseCommand` con helpers para SSM, RDS, procesos
- [x] Logger con colores (rich)

## Fase 1 — Comandos individuales
- [x] `yappy aws session` — AWS SSO login
- [x] `yappy aws mfa <user> <token>` — MFA session vía STS
- [x] `yappy db up <env>` — SSM tunnel a Aurora (con `--auto-refresh`)
- [x] `yappy db refresh <env>` — regenera token RDS + guarda en `.env.local`
- [x] `yappy ssm connect <port> <env> <cluster>` — port-forward genérico
- [x] `yappy ssm producer <env>` — tunnel a Kafka producer
- [x] `yappy ssm kafdrop <env>` — tunnel a Kafdrop UI
- [x] `yappy ssm databricks <env>` — tunnel a Databricks
- [x] `yappy ssm kill` — mata sesiones SSM
- [x] `yappy kafka up <server|ui|clean>` — Kafka management
- [x] `yappy kafka down` — detiene Kafka

## Fase 2 — Workflows compuestos
- [x] `yappy workflow debug-local <env>` — orquesta: AWS session → DB tunnel → Kafka → agents
- [x] `yappy db refresh <env>` — regenera token sin reiniciar tunnel
- [x] `yappy db up --auto-refresh` — refresca token automáticamente cada 12 min

## Fase 3 — Implementación nativa (COMPLETADA)
- [x] SSM tunnels vía `aws ssm start-session` directo (sin profile)
- [x] RDS auth token vía `aws rds generate-db-auth-token` directo
- [x] MFA vía `aws sts get-session-token` directo
- [x] Kafka vía subprocess directo a los `.bat` de Kafka
- [x] `kill_ssm` vía `taskkill`/`pkill`
- [x] Sin dependencia de scripts batch de `profile`

## Fase 4 — Calidad
- [ ] Tests unitarios (pytest)
- [ ] Autocompletado shell
- [ ] Setup/installer (`pip install .` o `pipx`)
