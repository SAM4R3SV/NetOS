# NetOS — Fase 1.1: revisión crítica del diseño arquitectónico

**Fecha de consulta:** 2026-11-02  
**Estado:** revisión externa; no autoriza implementación.  
**Alcance:** análisis documental y consulta de fuentes oficiales. No se
ejecutaron instaladores, pruebas de red ni comandos privilegiados.

## 1. Dictamen ejecutivo

El diseño de Fase 1 tiene una dirección correcta, especialmente en estos
puntos:

- separación conceptual entre plano de control y plano de datos;
- nftables como backend, en lugar de un firewall implementado en Python;
- integración de Suricata y Zeek como procesos externos;
- rechazo de DNS propio y DHCP propio;
- dashboard sin dependencia funcional para mantener las políticas.

Sin embargo, no está listo para autorizar implementación. Los problemas
principales son:

1. El límite entre `policies`, `firewall`, `gateway`, `lifecycle` y
   `persistence` todavía no define quién es la autoridad para aplicar cambios.
2. SQLite se propone a la vez para configuración, auditoría, inventario,
   eventos y telemetría, aunque WAL mantiene un único escritor.
3. La primera topología no está cerrada: sin dos interfaces o una topología
   explícitamente monitorizada no existe un gateway real.
4. Kea, Unbound/CoreDNS y el portal cautivo están descritos como posibilidades,
   no como perfiles mínimos con costes operativos concretos.
5. El coste de Zeek y Suricata en un i5-2400 no puede inferirse de la
   documentación general; deben quedar fuera del MVP de gateway hasta medir.
6. La persistencia del ruleset después de que Python/FastAPI fallen necesita un
   contrato de lifecycle independiente, no solo una promesa de “última
   política válida”.
7. El modelo de roles de NetOS necesita separarse explícitamente de usuarios,
   capabilities y permisos del sistema operativo.

**Recomendación:** aprobar únicamente un MVP local y controlado con modo
monitorización y un gateway IPv4 mínimo, nftables como aplicación declarativa,
SQLite solo para control/configuración y eventos de bajo volumen, sin IDS/IPS,
sin portal cautivo y sin cambios automáticos de interfaces. Todo lo demás debe
quedar detrás de adaptadores y fases posteriores.

## 2. Comprobación de referencias

### Referencias que sí respaldan las afirmaciones

| Afirmación del diseño | Resultado | Evidencia |
|---|---|---|
| nftables permite reemplazo atómico con `nft -f` | Respaldada | [Atomic rule replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement) describe cargar un fichero completo y hacer el intercambio en una operación |
| nftables permite tracing selectivo | Respaldada | [Ruleset tracing](https://wiki.nftables.org/wiki-nftables/index.php/Ruleset_debug/tracing) documenta `meta nftrace set 1` y `nft monitor trace` |
| Suricata es IDS/IPS/NSM | Respaldada | [Suricata: What is Suricata](https://docs.suricata.io/en/latest/what-is-suricata.html) |
| Zeek separa event engine y script interpreter | Respaldada | [Zeek architecture](https://docs.zeek.org/en/current/about/architecture.html) |
| CoreDNS usa cadenas de plugins | Respaldada | [CoreDNS plugins](https://coredns.io/manual/plugins/) |
| Kea proporciona DHCP y documentación de hooks/API | Respaldada | [Kea Administrator Reference Manual](https://kea.readthedocs.io/en/latest/) |
| Ubuntu Server usa una capa de configuración de red basada en Netplan | Respaldada | [Ubuntu: configuring networks](https://ubuntu.com/server/docs/explanation/networking/configuring-networks/) |
| systemd ofrece aislamiento, capabilities y directorios de estado | Respaldada | [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html) |
| FastAPI permite declarar seguridad mediante dependencias y documentar OAuth2/JWT | Respaldada | [FastAPI OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) |

### Referencias que requieren matización

| Afirmación | Problema |
|---|---|
| “SQLite puede servir para el primer núcleo” | Es razonable solo para configuración, inventario pequeño y auditoría acotada. La documentación oficial de [WAL](https://www.sqlite.org/wal.html) confirma concurrencia entre lectores y escritor, pero también que solo existe un escritor simultáneo, que WAL requiere el mismo host y que introduce checkpointing y ficheros auxiliares |
| “Suricata y Zeek son opcionales” | Es correcto arquitectónicamente, pero no basta para decidir su coste. Las páginas oficiales describen capacidades y modos, no un benchmark del i5-2400 con el ruleset y tráfico de NetOS |
| “Kea es preferido para gateway” | La documentación confirma capacidades, no que sea la mejor opción para una LAN pequeña ni que deba entrar en el MVP |
| “Unbound o CoreDNS” | Son alternativas de perfiles distintos. El diseño no debe conservar ambas como decisión abierta durante la implementación inicial |
| “Rollback nftables” | `nft -f` demuestra aplicación atómica, no un rollback operativo completo. El rollback exige almacenar una generación válida, validar ownership y definir qué ocurre si también falla el supervisor |
| “FastAPI + WebSocket” | La documentación confirma soporte, pero no resuelve por sí sola multi-proceso, backpressure, autenticación del canal ni entrega durable |

### Fuentes que deben añadirse al índice

- [SQLite WAL](https://www.sqlite.org/wal.html), para limitar correctamente el
  alcance de SQLite.
- [Suricata AF_PACKET](https://docs.suricata.io/en/latest/capture-hardware/af-packet.html),
  para distinguir captura y modo IPS.
- [Zeek architecture](https://docs.zeek.org/en/current/about/architecture.html),
  para separar generación de eventos de interpretación.
- [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html),
  para elegir `Type=exec/notify`, readiness y dependencias.
- [RFC 8981](https://www.rfc-editor.org/rfc/rfc8981), que confirma que las
  direcciones IPv6 temporales cambian y complican la identidad por dirección.

## 3. Problemas encontrados

### CR-01 — Autoridad de aplicación indefinida

- **Severidad:** crítica.
- **Evidencia:** el diseño asigna funciones a `policies`, `firewall`,
  `gateway`, `lifecycle` y `api`, pero no define un único dueño de la
  generación aplicada.
- **Riesgo:** dos procesos podrían intentar aplicar configuraciones distintas,
  o el API podría registrar “aplicado” antes de que el adaptador privilegiado
  termine.
- **Alternativas:**
  1. API llama directamente a un helper privilegiado.
  2. API escribe una intención y un reconciler único aplica el estado deseado.
  3. systemd/D-Bus administra el servicio privilegiado.
- **Recomendación:** usar un **reconciler único del plano de datos**. La API
  persiste una intención versionada; el reconciler valida, compila, aplica y
  confirma una generación. Ningún otro proceso ejecuta `nft` o `ip`.
- **Cambio propuesto:** añadir `desired_state`, `applied_state`,
  `generation`, `owner` y `apply_status` como conceptos de dominio. El API
  nunca debe afirmar que una política está aplicada solo porque fue aceptada.

### CR-02 — La persistencia mezcla configuración con telemetría

- **Severidad:** alta.
- **Evidencia:** el modelo incluye `Connection`, `DnsQuery`, `SecurityAlert`,
  `AuditEvent`, inventario y políticas dentro de la misma estrategia de
  persistencia.
- **Riesgo:** ráfagas de eventos pueden bloquear cambios administrativos,
  agrandar la base y hacer impredecible el tiempo de consulta.
- **Referencia:** [SQLite WAL](https://www.sqlite.org/wal.html) mantiene un
  único escritor y requiere checkpointing.
- **Alternativas:**
  1. SQLite para todo.
  2. SQLite para estado/control y ficheros rotados para telemetría.
  3. SQLite para control y backend externo opcional para alta retención.
- **Recomendación:** opción 2 para MVP. Persistir en SQLite políticas,
  despliegues, identidad, inventario pequeño y auditoría; guardar eventos de
  sensores y conexiones en logs estructurados rotados, con índices derivados
  solo si una necesidad real aparece.
- **Cambio propuesto:** declarar SQLite como **control-plane store**, no como
  almacén general de observabilidad.

### CR-03 — El gateway no está condicionado a una topología real

- **Severidad:** crítica.
- **Evidencia:** el diseño menciona WAN/LAN, routing y NAT, pero no establece
  el número mínimo de interfaces, VLAN, bridge ni modo de prueba.
- **Riesgo:** desplegar en una sola NIC conectada al router ISP no convierte
  automáticamente al servidor en gateway y puede provocar doble DHCP, pérdida
  de acceso o una política aplicada al segmento equivocado.
- **Referencia:** [Ubuntu network configuration](https://ubuntu.com/server/docs/explanation/networking/configuring-networks/)
  documenta la capa de configuración, pero no valida la topología específica
  de NetOS.
- **Recomendación:** MVP con dos perfiles explícitos:
  - `monitor`: una interfaz, sin forwarding/NAT.
  - `gateway-lab`: dos interfaces físicas o namespaces/veth, IPv4 solamente.
- **Cambio propuesto:** bloquear el modo gateway si el preflight no confirma
  interfaces, direccionamiento y ownership de DHCP/DNS.

### CR-04 — Kea es demasiado grande como decisión predeterminada de MVP

- **Severidad:** media-alta.
- **Evidencia:** Kea se presenta como preferido aunque la primera topología es
  una LAN pequeña y el proyecto aún no ha definido DHCPv6, reservas masivas,
  HA ni múltiples segmentos.
- **Riesgo:** añadir un servicio, su API, configuración, lifecycle y
  troubleshooting antes de demostrar que se necesita.
- **Alternativas:**
  1. Kea desde el primer gateway.
  2. dnsmasq como perfil mínimo de una sola LAN.
  3. DHCP fuera de NetOS inicialmente, modo monitor.
- **Recomendación:** no incluir DHCP administrado en el MVP de monitorización.
  Para gateway-lab, empezar con una interfaz de `DhcpProvider` y seleccionar
  dnsmasq o Kea tras validar requisitos de reservas, DHCPv6 y persistencia.
  No implementar servidor propio.

### CR-05 — Unbound y CoreDNS no deben permanecer como “alternativa abierta”

- **Severidad:** media.
- **Evidencia:** el diseño asigna a ambos el mismo punto de decisión aunque
  tienen modelos distintos: Unbound como resolver recursivo/cacheado y
  CoreDNS como cadena de plugins.
- **Riesgo:** una abstracción demasiado amplia obliga a soportar dos modelos de
  configuración y health sin una necesidad demostrada.
- **Recomendación:** para gateway-lab de una sola LAN, seleccionar Unbound si
  el requisito es resolver/cache/validación; seleccionar CoreDNS solo si el
  requisito aprobado es pipeline de plugins, split DNS o extensibilidad. El
  MVP debe elegir uno.
- **Cambio propuesto:** `ResolverProvider` mínimo con `configure`, `validate`,
  `reload`, `health`; un único adaptador inicial.

### CR-06 — Suricata y Zeek deben quedar fuera del MVP de gateway

- **Severidad:** alta.
- **Evidencia:** el i5-2400 tiene cuatro núcleos físicos de una generación
  antigua; las fuentes oficiales describen capacidades de Suricata/Zeek, pero
  no garantizan throughput para ese hardware.
- **Referencia:** [Suricata AF_PACKET](https://docs.suricata.io/en/latest/capture-hardware/af-packet.html)
  documenta la interfaz de captura y opciones, no una cifra universal de
  rendimiento. [Zeek architecture](https://docs.zeek.org/en/current/about/architecture.html)
  muestra que procesa paquetes, sesiones, protocolos, ficheros y scripts.
- **Riesgo:** combinar routing, conntrack, NAT, IPS y Zeek puede saturar CPU,
  aumentar latencia y crear pérdida de paquetes sin que el firewall lo
  refleje.
- **Recomendación:** MVP sin Zeek y sin IPS. Permitir Suricata IDS posterior
  en modo observación, con medición de CPU, drops y latencia. Zeek queda como
  perfil de sensor separado, no como proceso obligatorio del gateway.

### CR-07 — Persistencia del ruleset después del fallo incompleta

- **Severidad:** crítica.
- **Evidencia:** el diseño describe `nft -f`, generaciones y rollback, pero no
  define quién restaura el ruleset al arranque ni qué pasa si Python muere
  después de aplicar una generación.
- **Riesgo:** reinicio del host, corrupción de estado o caída del reconciler
  pueden dejar reglas antiguas sin registro, reglas no persistidas o una
  diferencia entre DB y kernel.
- **Referencia:** [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
  documenta lifecycle/readiness; no proporciona por sí solo el modelo de
  estado de NetOS.
- **Recomendación:** el ruleset aplicado debe ser un artefacto independiente,
  versionado y cargable por un servicio de restauración de bajo privilegio
  controlado por systemd. Al arranque: verificar checksum, versión de
  nftables, interfaces y ownership; cargar solo si el preflight coincide.
- **Cambio propuesto:** separar `policy compiler` de `policy-applier`; el
  applier debe poder restaurar la última generación válida sin FastAPI.

### CR-08 — Dependencias circulares latentes

- **Severidad:** alta.
- **Evidencia:** `inventory` produce eventos para `observability`, `policies`
  consume inventario, `firewall` produce estado para `observability` y
  `persistence` aparece como dependencia de casi todos.
- **Riesgo:** importaciones circulares, inicialización acoplada y dificultad de
  probar componentes sin arrancar todo el sistema.
- **Recomendación:** usar contratos y puertos:
  - dominio no importa adaptadores;
  - `events` define esquemas, no conoce consumidores;
  - `observability` consume eventos, no es requisito para publicar una
    política;
  - `persistence` implementa repositorios, no define reglas de negocio;
  - un composition root conecta todo.
- **Cambio propuesto:** distinguir `domain`, `application`, `ports` y
  `adapters` aunque los paquetes sigan agrupados por capacidad.

### CR-09 — Roles de NetOS y privilegios del SO no están separados

- **Severidad:** alta.
- **Evidencia:** los roles propuestos incluyen `system-admin`, mientras la
  arquitectura también contempla `netos-firewall` y capabilities de systemd.
- **Riesgo:** interpretar que un rol HTTP puede equivaler a root, o que el
  usuario Unix del servicio representa un administrador de NetOS.
- **Referencia:** [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
  documenta sandboxing y filesystem; [Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)
  separa privilegios del proceso, no roles de aplicación.
- **Recomendación:** dos modelos independientes:
  - RBAC/ABAC de NetOS: acciones sobre recursos y segmentos.
  - identidad Unix/capabilities: permisos mínimos de procesos.
  No exponer un rol web que otorgue capabilities; el applier aplica solo
  operaciones predefinidas y validada.

### CR-10 — IPv6, identidades temporales y MAC aleatorias están submodeladas

- **Severidad:** alta.
- **Evidencia:** el diseño incluye `family: ipv4/ipv6/both`, pero el inventario
  usa `mac`, `DeviceAddress` y `stable_identity` sin definir confianza o
  rotación.
- **Referencia:** [RFC 8981](https://www.rfc-editor.org/rfc/rfc8981) define
  direcciones IPv6 temporales con identificadores aleatorios que cambian con
  el tiempo.
- **Riesgo:** usar IP, MAC o una sola dirección como identidad produce
  duplicados, pérdida de continuidad o autorización incorrecta.
- **Recomendación:** tratar la identidad como evidencia con nivel de confianza:
  `link_observation`, `dhcp_lease`, `ipv6_address`, `mac`, `hostname`,
  `authenticated_subject`. Las políticas de acceso deben estar ligadas a una
  entidad y segmento, no a una IP estable asumida.
- **Cambio propuesto:** añadir expiración, fuente, confianza y observación
  temporal a direcciones/MAC; prohibir que una MAC aleatoria se fusione
  automáticamente con un dispositivo anterior.

### CR-11 — API y comunicación entre procesos están sobrediseñadas para MVP

- **Severidad:** media.
- **Evidencia:** el documento deja abiertas WebSocket, polling durable,
  Unix socket y broker; también enumera múltiples recursos desde el inicio.
- **Riesgo:** se implementa una plataforma distribuida antes de validar el
  flujo local de políticas.
- **Recomendación:** MVP con:
  - API REST para comandos y consultas;
  - Unix socket privado entre API y applier, con protocolo versionado;
  - polling de estado de aplicación;
  - SSE o polling para eventos del dashboard, no WebSocket obligatorio;
  - eventos de auditoría síncronos y eventos de telemetría best-effort.
- **Optimización:** separar lecturas de estado actual de consultas históricas;
  usar paginación por cursor, índices por timestamp/estado y límites
  estrictos. No añadir caché distribuida sin perfil de carga.

### CR-12 — Dashboard demasiado amplio para el primer operador

- **Severidad:** media.
- **Evidencia:** la navegación propuesta contiene gateway, segmentos, VLAN,
  políticas, conexiones, DNS, IDS/IPS, portal, usuarios, auditoría y
  mantenimiento.
- **Riesgo:** baja discoverability, exceso de densidad y peligro de cambios
  operativos desde una pantalla de resumen.
- **Recomendación:** MVP de cuatro áreas:
  1. Overview/health;
  2. dispositivos e interfaces;
  3. políticas con diff/preflight/aplicar;
  4. eventos/auditoría.
  Servicios DNS/DHCP, IDS/IPS, portal y notificaciones deben aparecer como
  capacidades opcionales cuando estén instaladas.
- **Cambio propuesto:** la pantalla Overview no debe tener acciones
  destructivas; aplicar políticas requiere una vista de diff y confirmación.

### CR-13 — El portal cautivo añade complejidad y no es necesario para validar el core

- **Severidad:** media-alta.
- **Evidencia:** el portal se mantiene como módulo futuro, pero aparece en
  objetivos y navegación.
- **Riesgo:** mezcla identidad humana, identidad de dispositivo y enforcement
  de red; además exige tratar IPv6, DoH, detección de sistemas operativos y
  excepciones.
- **Recomendación:** posponerlo hasta que el gateway, inventario, políticas y
  rollback estén validados. Si se implementa, debe ser un adaptador de
  onboarding que solicite una autorización al motor de políticas.

## 4. Dependencias y límites revisados

### Dependencias permitidas

```text
domain contracts
      ^
application services
      ^
adapters: persistence / nftables / gateway / DNS / DHCP / sensors
      ^
composition root
      ^
API / CLI / systemd units / dashboard
```

Reglas:

- `domain` no importa FastAPI, SQLAlchemy, subprocess ni systemd.
- `api` no ejecuta `nft`, `ip`, Kea, DNS ni Suricata.
- `dashboard` solo conoce contratos versionados de API.
- `observability` no es una dependencia de seguridad cuyo fallo impida
  aplicar una política.
- `events` no importa consumidores.
- `persistence` no conoce el proceso que utiliza los repositorios.
- Solo `policy-applier` puede comunicarse con el adaptador nftables.
- Solo el composition root construye y conecta adaptadores.

## 5. Arquitectura MVP recomendada

### Objetivo

Validar de forma segura el control de políticas, inventario y operación local
sin convertir el HP Compaq 6200 Pro en un sensor IDS/IPS completo.

### Perfil M0: monitorización

- Una interfaz existente.
- Inventario básico de interfaces y dispositivos observables.
- SQLite para configuración, inventario y auditoría acotada.
- API REST local.
- Dashboard local mínimo.
- Sin cambios en routing, NAT, DHCP, DNS ni nftables.
- Logs estructurados y health checks.

### Perfil M1: gateway de laboratorio

- Dos interfaces o namespaces de red controlados.
- IPv4 primero; IPv6 solo después de aprobar el modelo de identidad y reglas.
- nftables con tabla/namespace propio de NetOS.
- `policy-applier` único y separado de FastAPI.
- Generaciones de ruleset con checksum, preflight y rollback.
- DHCP/DNS mediante un solo adaptador seleccionado, no ambos.
- Sin portal cautivo.
- Sin Zeek.
- Suricata IDS solo como experimento posterior, desactivado por defecto.

### Procesos

```text
netos-api              usuario sin privilegios
netos-control          usuario sin privilegios
netos-policy-applier   servicio mínimo y privilegiado
netos-inventory        usuario sin privilegios
resolver/dhcp          servicios externos seleccionados
systemd                supervisión, restauración y sandboxing
```

El applier no acepta comandos arbitrarios; recibe una generación declarativa,
validada y limitada por el contrato.

## 6. Funcionalidades que deben esperar

Posponer hasta completar benchmarks y pruebas de recuperación:

1. IPS inline con Suricata.
2. Zeek local obligatorio.
3. Portal cautivo.
4. Soporte multi-sitio.
5. HA y múltiples nodos.
6. PostgreSQL, Redis, Kafka o Celery.
7. DHCPv6 y automatización IPv6 completa.
8. Reglas temporales complejas y scheduler de políticas.
9. Integraciones Telegram/email/webhook.
10. Exportaciones analíticas de alto volumen.
11. Dashboard de conexiones históricas de alta cardinalidad.
12. Cambios automáticos de Netplan, bridges, VLAN y rutas desde la UI.
13. Compatibilidad OpenWrt.
14. Promesa de 1 Gbps.

## 7. Cambios concretos propuestos al diseño

1. Añadir un capítulo de **composition root y reconciler**.
2. Reemplazar “SQLite inicialmente” por “SQLite para control-plane; telemetría
   fuera hasta medir”.
3. Convertir `gateway-lab` y `monitor` en perfiles explícitos.
4. Elegir un solo proveedor inicial de DNS y DHCP por perfil.
5. Definir el applier de nftables como servicio autónomo restaurable.
6. Separar RBAC de NetOS de Unix users/capabilities.
7. Añadir confianza y expiración a identidades MAC/IP/IPv6.
8. Reducir el dashboard MVP a cuatro áreas operativas.
9. Añadir un contrato mínimo de IPC local y evitar broker externo.
10. Introducir una matriz de aceptación antes de afirmar soporte de 1 Gbps.
11. Añadir las fuentes SQLite, Suricata AF_PACKET, Zeek architecture y
    systemd.service a `docs/references.md`.
12. Registrar una decisión formal para dejar OpenNDS/portal fuera del MVP.

## 8. Decisiones que requieren aprobación

1. ¿Se aprueba el alcance MVP `monitor` + `gateway-lab`, sin gateway
   automático sobre la red real?
2. ¿Se acepta SQLite solo para control-plane y no para telemetría de alta
   cardinalidad?
3. ¿Se designa un único `policy-applier` como autoridad de nftables?
4. ¿Se acepta IPv4 primero y IPv6 como fase posterior?
5. ¿Se excluyen Suricata IPS, Zeek y portal cautivo del MVP?
6. ¿Se permite usar dnsmasq o Kea solo después de definir requisitos DHCP?
7. ¿Se acepta SSE/polling antes de WebSocket?
8. ¿Se aprueba separar formalmente roles NetOS de usuarios/capabilities del SO?
9. ¿Se acepta que la UI no modifique interfaces, rutas o firewall sin
   preflight, diff, confirmación y rollback?
10. ¿Qué criterio medible de throughput, latencia y pérdida autorizaría afirmar
    soporte de 1 Gbps?

## 9. Conclusión

La arquitectura de Fase 1 es una base útil, pero todavía es un mapa de
capacidades y no un diseño implementable sin riesgo. La prioridad debe ser
reducir superficie:

```text
identidad + inventario + políticas
        -> reconciler único
        -> nftables versionado
        -> gateway de laboratorio
```

El dashboard, DHCP/DNS, portal, Suricata y Zeek deben conectarse después como
adaptadores con criterios de aceptación propios. No recomiendo autorizar aún
la implementación de servicios de producción hasta resolver las decisiones de
la sección 8.

