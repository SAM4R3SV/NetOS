# Decisiones y cuestiones pendientes

Esta carpeta registra decisiones técnicas del proyecto nuevo. Ninguna decisión
de esta fase configura el sistema operativo ni aplica reglas de red.

## Decisiones iniciales

| ID | Decisión | Estado |
|---|---|---|
| D-001 | Python es el lenguaje principal del backend | Propuesta |
| D-002 | Ubuntu Server es la primera plataforma objetivo | Propuesta |
| D-003 | El backend se divide en plano de control y plano de datos | Propuesta |
| D-004 | nftables será el backend de firewall previsto | Pendiente de diseño |
| D-005 | El dashboard no será dependencia del plano de datos | Propuesta |
| D-006 | `NetOS_obsolete/` no se modifica ni se usa como plantilla automática | Aprobada por alcance |

## Índice de decisiones de Fase 1.2

Las decisiones cerradas, su justificación, dependencias y condiciones de
reconsideración están documentadas en
[phase1.2-architecture-decisions.md](../phase1.2-architecture-decisions.md).

| ID | Decisión | Documento |
|---|---|---|
| D-101 | Perfiles `monitor` y `gateway-lab` separados | [Fase 1.2](../phase1.2-architecture-decisions.md#2-alcance-del-modo-monitor) |
| D-102 | `monitor` no muta tráfico ni configuración de red | [Fase 1.2](../phase1.2-architecture-decisions.md#2-alcance-del-modo-monitor) |
| D-103 | `gateway-lab` requiere activación y preflight | [Fase 1.2](../phase1.2-architecture-decisions.md#3-activación-y-condiciones-de-gateway-lab) |
| D-104 | Reconciler único como autoridad del plano de datos | [Fase 1.2](../phase1.2-architecture-decisions.md#4-reconciler-y-policy-applier) |
| D-105 | Solo `policy-applier` modifica nftables | [Fase 1.2](../phase1.2-architecture-decisions.md#4-reconciler-y-policy-applier) |
| D-106 | Unix socket local versionado entre API y applier | [Fase 1.2](../phase1.2-architecture-decisions.md#5-comunicación-api--proceso-privilegiado) |
| D-107 | SQLite limitado al control-plane | [Fase 1.2](../phase1.2-architecture-decisions.md#6-persistencia-y-límites-de-sqlite) |
| D-108 | Telemetría en logs rotados o backend futuro | [Fase 1.2](../phase1.2-architecture-decisions.md#7-logs-telemetría-y-retención) |
| D-109 | Identidad basada en evidencias con confianza y expiración | [Fase 1.2](../phase1.2-architecture-decisions.md#8-identidad-de-dispositivos) |
| D-110 | RBAC NetOS separado de privilegios Unix | [Fase 1.2](../phase1.2-architecture-decisions.md#9-autenticación-autorización-y-privilegios) |
| D-111 | Último ruleset válido independiente de FastAPI | [Fase 1.2](../phase1.2-architecture-decisions.md#10-recuperación-y-último-ruleset-válido) |
| D-112 | Sin portal, Zeek ni Suricata IPS en el MVP | [Fase 1.2](../phase1.2-architecture-decisions.md#14-dependencias-y-condiciones-de-reconsideración) |
| D-113 | IPv6 modelado, pero no activo en gateway MVP | [Fase 1.2](../phase1.2-architecture-decisions.md#3-activación-y-condiciones-de-gateway-lab) |
| D-114 | Dashboard MVP de cuatro áreas | [Arquitectura MVP](../architecture/mvp-architecture.md#8-dashboard-mvp) |
| D-115 | Sin promesa de 1 Gbps sin benchmarks | [Fase 1.2](../phase1.2-architecture-decisions.md#13-métricas-y-criterios-de-hardware) |

## Criterios de aceptación

Los criterios verificables del MVP están en
[phase1.2-acceptance-criteria.md](../phase1.2-acceptance-criteria.md).

La arquitectura visual y los límites de módulos del MVP están en
[mvp-architecture.md](../architecture/mvp-architecture.md).

## Cuestiones que requieren aprobación antes de implementar

1. Aprobar el alcance `monitor` + `gateway-lab` IPv4 como MVP.
2. Aprobar la activación del gateway solo en laboratorio aislado.
3. Aprobar los umbrales concretos de rendimiento y latencia.
4. Seleccionar el proveedor inicial de DNS y DHCP cuando se cierre la topología.
5. Aprobar el procedimiento operativo de recuperación y rollback.
6. Confirmar la política de retención de auditoría y telemetría.
7. Confirmar el modelo inicial de roles administrativos.
8. Autorizar explícitamente el inicio de implementación.

## Decisiones concretadas en Fase 2.1

| Tema | Decisión | Alcance |
|---|---|---|
| API | FastAPI + Uvicorn | Solo API local de lectura y salud |
| Configuración | Variables `NETOS_*` con defaults seguros | Sin secretos ni credenciales predeterminadas |
| Persistencia | `sqlite3` de la biblioteca estándar | Estado y auditoría acotada; no telemetría ilimitada |
| Migraciones | Scripts versionados internos | Idempotentes y ejecutados al inicializar |
| Logging | JSON + rotación diaria | Retención configurable, 30 días por defecto |
| Pruebas | pytest + TestClient | Unitarias e integración sin red ni privilegios |

Estas decisiones no autorizan todavía gateway, firewall, reconciler,
`policy-applier` ni cambios en el sistema operativo.
