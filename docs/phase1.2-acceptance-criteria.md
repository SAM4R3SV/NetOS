# NetOS — Fase 1.2: criterios de aceptación del MVP

**Fecha:** 2026-11-02  
**Estado:** criterios para pruebas futuras; no se han ejecutado.

Un resultado no se considera aprobado por inspección documental. Cada criterio
requiere evidencia reproducible en un entorno de laboratorio.

## 1. Criterios funcionales

### Perfil monitor

- [ ] Arranca en modo `monitor` sin activar forwarding.
- [ ] No modifica interfaces, rutas, Netplan, DNS, DHCP, NAT ni nftables.
- [ ] Un inventario de lectura identifica interfaces y registra freshness.
- [ ] La caída del dashboard no afecta observación ni estado previamente
      aplicado.
- [ ] Las operaciones de escritura son rechazadas aunque el usuario de API
      tenga un rol administrativo de NetOS.

### Perfil gateway-lab

- [ ] Requiere activación explícita.
- [ ] Requiere dos interfaces o namespaces/veth de laboratorio.
- [ ] Rechaza subredes solapadas, ownership ambiguo y canal de recuperación
      ausente.
- [ ] No se activa con preflight fallido.
- [ ] El gateway inicial opera solo con el alcance IPv4 aprobado.
- [ ] IPv6 se observa o se rechaza explícitamente, pero no queda permitido por
      accidente.

## 2. Criterios de políticas y nftables

- [ ] Cada aplicación recibe un `generation_id` único y un hash verificable.
- [ ] El documento de política se valida antes de generar reglas.
- [ ] Los conflictos de prioridad, segmento o acción bloquean la aplicación.
- [ ] Solo `policy-applier` puede comunicarse con nftables.
- [ ] La API no acepta comandos arbitrarios ni shell.
- [ ] La aplicación usa una operación atómica del backend seleccionado.
- [ ] Se registra actor, intención, preflight, generación y resultado.
- [ ] La API no informa `applied` antes de recibir confirmación del applier.
- [ ] Un cambio fallido conserva la última generación válida.
- [ ] No existe una ruta automática de fallo hacia `allow all`.

## 3. Criterios de comunicación entre procesos

- [ ] El Unix socket tiene propietario y permisos restrictivos.
- [ ] El protocolo rechaza versiones incompatibles.
- [ ] Cada solicitud tiene timeout y correlation ID.
- [ ] Mensajes sobredimensionados o desconocidos son rechazados.
- [ ] Un applier no disponible produce estado `degraded`, no éxito falso.
- [ ] Reiniciar FastAPI no elimina ni modifica el último ruleset aplicado.
- [ ] Reiniciar el applier restaura o conserva una generación válida.

## 4. Criterios de persistencia

- [ ] Las migraciones se ejecutan de forma versionada e idempotente.
- [ ] Las transacciones de control son cortas.
- [ ] Un bloqueo SQLite produce un error observable y accionable.
- [ ] El sistema no usa SQLite para telemetría ilimitada.
- [ ] Existen cuotas y retención para auditoría y logs.
- [ ] Un backup se puede restaurar en un entorno temporal.
- [ ] Un restore no modifica la red ni aplica reglas automáticamente.
- [ ] WAL, si se habilita, se valida con el patrón real de acceso.

## 5. Criterios de identidad de dispositivos

- [ ] IP, MAC, DHCP, hostname e IPv6 se almacenan como evidencias separadas.
- [ ] Cada evidencia incluye fuente, timestamp, confianza y expiración cuando
      corresponda.
- [ ] Cambiar de IP no crea duplicados automáticamente.
- [ ] Una MAC aleatoria no se fusiona automáticamente con un dispositivo
      histórico.
- [ ] Una IPv6 temporal puede expirar sin invalidar la entidad completa.
- [ ] Las políticas no dependen de una sola IP supuestamente estable.
- [ ] Las correlaciones inciertas se muestran como inciertas.

## 6. Criterios de seguridad

- [ ] API, control e inventario no se ejecutan como root.
- [ ] Las capabilities del applier están documentadas y son mínimas.
- [ ] El RBAC de NetOS no cambia permisos Unix.
- [ ] Las operaciones de aplicación requieren el permiso específico.
- [ ] Las mutaciones con cookie tienen protección CSRF.
- [ ] Las sesiones tienen expiración, revocación y auditoría.
- [ ] Tokens, contraseñas y secretos no aparecen en logs, URLs ni argumentos.
- [ ] Los servicios aplican sandboxing compatible con sus necesidades.
- [ ] El dashboard no carga recursos externos en producción.
- [ ] El dashboard no inserta datos de inventario sin escape.

## 7. Criterios de recuperación

- [ ] Existe un artefacto `last-known-good` fuera de la API.
- [ ] El artefacto tiene hash, generación, versión y ownership.
- [ ] Un arranque puede restaurar una generación válida sin FastAPI.
- [ ] Un artefacto corrupto deja el sistema en `degraded` y no aplica datos
      ambiguos.
- [ ] Un fallo de health después de aplicar dispara rollback controlado.
- [ ] El procedimiento manual de recuperación está documentado.
- [ ] La desinstalación no elimina recursos de terceros.
- [ ] La desinstalación preserva datos por defecto y permite exportarlos.

## 8. Criterios del dashboard

- [ ] La navegación inicial contiene Overview, Inventario, Políticas y
      Auditoría.
- [ ] Overview no contiene acciones destructivas.
- [ ] Una política muestra diff, preflight, confirmación y generación.
- [ ] El estado `planned`, `applying`, `applied`, `failed`, `rolled_back` y
      `degraded` es visible.
- [ ] Las tablas tienen filtros, límites y paginación.
- [ ] Los errores explican la acción que puede tomar el operador.
- [ ] La interfaz es usable con teclado y contraste suficiente.
- [ ] La UI funciona sin acceso a Internet.

## 9. Pruebas requeridas

### Unitarias

- modelos de configuración;
- RBAC y autorización;
- evidencias de identidad;
- normalización de políticas;
- detección de conflictos;
- hashes y generaciones;
- protocolo IPC;
- estados de apply/rollback;
- migraciones y repositorios.

### Integración

- API con DB temporal;
- autenticación, revocación y CSRF;
- API–reconciler–applier simulado;
- timeouts, errores y reintentos;
- restart de API y applier;
- backup/restore;
- sandbox y permisos.

### Laboratorio de red

- namespaces/veth o hardware aislado;
- monitor sin mutaciones;
- gateway IPv4;
- NAT/forwarding;
- políticas permitidas y denegadas;
- cambio de generación;
- rollback;
- caída de FastAPI;
- caída del applier;
- reinicio del host;
- interfaces ausentes;
- subredes solapadas;
- observación IPv6 y comprobación de ausencia de bypass accidental.

No se ejecutarán pruebas destructivas contra la red real.

## 10. Criterios de rendimiento

No existe todavía un número de throughput aprobado. Antes de declarar soporte
se deben medir:

- routing IPv4 sin firewall;
- NAT;
- nftables con conntrack;
- número y tipo de reglas;
- sets/maps;
- conexiones simultáneas;
- tasa de eventos;
- API y tiempos del applier;
- uso de CPU/RAM;
- latencia p50/p95/p99;
- pérdida y drops;
- actividad del HDD;
- recuperación y checkpoint de SQLite.

Cada resultado debe incluir versión de Ubuntu/kernel/nftables, NIC, tamaño de
paquete, número de flujos, reglas, configuración y duración. El i5-2400 no se
considera apto para 1 Gbps hasta que el escenario concreto lo demuestre.

## 11. Condiciones para autorizar el gateway experimental

El gateway-lab solo puede autorizarse cuando:

1. monitor pasa todos sus criterios de no mutación;
2. existen dos interfaces o laboratorio aislado;
3. el preflight detecta correctamente topología y ownership;
4. el applier funciona sin FastAPI;
5. una política válida se aplica y se identifica por generación;
6. una política inválida no cambia nftables;
7. rollback está probado;
8. caída de API conserva el ruleset;
9. reinicio restaura la última generación válida;
10. no hay secretos en logs o procesos;
11. IPv6 no puede atravesar accidentalmente el gateway MVP;
12. existen métricas de CPU, RAM, latencia, drops y disco;
13. el procedimiento de recuperación ha sido probado;
14. el propietario aprueba explícitamente el entorno de laboratorio.

## 12. Criterios fuera del MVP

No son criterios de finalización del MVP:

- portal cautivo;
- Suricata IPS;
- Zeek obligatorio;
- DHCPv6;
- segmentación avanzada y VLAN automáticas;
- multi-sitio;
- HA;
- backend distribuido;
- rendimiento de 1 Gbps;
- compatibilidad OpenWrt.

