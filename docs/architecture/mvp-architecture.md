# NetOS MVP — arquitectura aprobada para diseño

**Estado:** diseño cerrado; no es implementación.  
**Fecha:** 2026-11-02

## 1. Componentes

```text
                         Plano de control

  Dashboard / CLI
        |
        v
  netos-api --------------------+
        |                        |
        v                        v
  Identity / RBAC          Application services
        |                        |
        +------------+-----------+
                     v
              Control-plane DB
              (SQLite limitado)
                     |
                     v
              Desired generations
                     |
                     v
              Reconciler único
                     |
             Unix socket local
                     |
                     v
             policy-applier
             (privilegio mínimo)
                     |
                     v
              nftables / kernel

                         Plano de datos
  Interfaces -> routing/NAT -> nftables -> forwarding
       |
       +--> inventory observer -> events -> logs/health
```

Los procesos futuros de DHCP, DNS, Suricata, Zeek y portal se conectarán como
adaptadores o servicios externos. No forman parte del camino obligatorio del
MVP.

## 2. Perfiles de ejecución

### Monitor

```text
read-only OS adapters -> inventory -> control-plane DB -> API/dashboard
```

No modifica tráfico, interfaces, rutas, Netplan, DHCP, DNS ni nftables.

### Gateway-lab

```text
WAN <-> gateway-lab <-> LAN
              |
              +--> policy-applier -> nftables
              +--> selected DNS/DHCP provider
```

Solo se activa explícitamente después de un preflight. El primer gateway
funcional es IPv4 y debe ejecutarse en dos interfaces o namespaces de
laboratorio.

## 3. Límites entre módulos

| Módulo | Puede hacer | No puede hacer |
|---|---|---|
| API | validar solicitudes, autorizar, crear intenciones, leer estado | ejecutar comandos de sistema o afirmar apply sin confirmación |
| Identity/RBAC | autenticar y autorizar acciones NetOS | otorgar root/capabilities Unix |
| Inventory | observar interfaces/dispositivos y producir evidencias | alterar interfaces o aplicar políticas |
| Persistence | guardar contratos y generaciones | decidir reglas de negocio por efectos laterales |
| Policies | validar, normalizar y compilar estado deseado | escribir nftables |
| Reconciler | coordinar preflight, compilación y apply | aceptar comandos arbitrarios |
| Policy-applier | aplicar/restaurar la generación validada | aceptar shell, rutas o reglas no declaradas |
| Gateway | describir y validar topología | alterar el host fuera de su contrato |
| Events | transportar contratos versionados | conocer consumidores concretos |
| Observability | registrar y medir | bloquear silenciosamente el plano de datos |
| Dashboard | presentar y solicitar operaciones | acceder al kernel o a SQLite directamente |

Dependencias:

```text
domain -> application -> ports -> adapters
                      ^
                  composition root
```

No hay importaciones de FastAPI, subprocess o systemd desde el dominio.

## 4. Interfaces principales

### Control-plane

```text
create_intent(document, actor) -> intent_id
validate_intent(intent_id) -> validation_report
plan_generation(intent_id) -> generation_plan
request_apply(generation_id, confirmation) -> apply_request_id
get_apply_status(request_id) -> apply_status
rollback(generation_id, reason) -> rollback_status
```

### Policy-applier

```text
preflight(generation) -> preflight_report
apply(generation) -> applied_generation
restore(last_known_good) -> restore_status
health() -> applier_health
```

El protocolo del Unix socket debe incluir versión, correlation ID, timeout,
estado y error tipado. No incluye una operación `execute(command)`.

### Observación

```text
observe_interfaces() -> interface_evidence[]
observe_devices() -> device_evidence[]
publish_event(event) -> delivery_status
```

## 5. Flujo completo de aplicación de políticas

```text
1. Usuario autenticado envía documento a API.
2. API autoriza la acción y valida el esquema.
3. Se guarda una intención inmutable.
4. Policies normaliza y detecta conflictos.
5. Reconciler verifica topología, ownership y canal administrativo.
6. Se crea generation_id y hash del documento.
7. Policies compila el ruleset declarativo.
8. El applier valida sintaxis y precondiciones.
9. API solicita confirmación explícita si el cambio es de riesgo.
10. Reconciler envía solo la generación validada por Unix socket.
11. Applier carga el ruleset de forma atómica.
12. Applier ejecuta health checks.
13. Si todo es correcto, registra applied_generation.
14. Si falla, restaura last-known-good y registra rollback.
15. API muestra apply, rollback o degraded sin falsear éxito.
```

## 6. Flujo de recuperación

```text
Arranque systemd
      |
      v
restore service lee last-known-good
      |
      +--> checksum/version/ownership inválido -> degraded + no apply
      |
      v
preflight de interfaces y compatibilidad
      |
      +--> fallo -> conservar estado seguro y alertar
      |
      v
carga atómica de generación válida
      |
      v
health check
      |
      +--> fallo -> rollback/restore previo
      |
      v
ready
```

La caída de FastAPI no elimina las reglas. La caída del applier tampoco debe
provocar un `allow all` automático.

## 7. Persistencia y eventos

SQLite contiene:

- configuración;
- identidad administrativa;
- inventario pequeño;
- intenciones;
- generaciones;
- estado de aplicación;
- auditoría limitada.

Los eventos de alta cardinalidad se escriben en logs rotados con cuota. En el
MVP, el dashboard consulta estado actual y auditoría; no ofrece exploración
ilimitada de tráfico.

## 8. Dashboard MVP

1. **Overview:** salud, modo activo, generación aplicada y alertas operativas.
2. **Inventario:** interfaces, dispositivos y evidencias con freshness.
3. **Políticas:** documento, diff, preflight, confirmación y estado.
4. **Auditoría/eventos:** cambios, autenticación, apply y rollback.

No se muestran controles de gateway destructivos en Overview. DNS, DHCP,
Suricata, Zeek, portal y notificaciones aparecerán solo si un adaptador futuro
está instalado y reporta health.

