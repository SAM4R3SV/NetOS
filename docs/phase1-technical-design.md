# NetOS — Fase 1: investigación técnica y diseño arquitectónico

Estado: propuesta pendiente de aprobación.  
Alcance: investigación y diseño; no implementa servicios ni configura el sistema.

## 1. Resumen ejecutivo

NetOS debe diseñarse como una plataforma de control de redes Linux, no como
un daemon monolítico que intente reemplazar el kernel, DHCP, DNS, firewall o
los sensores de seguridad. La recomendación es separar:

- **Plano de control:** API, identidad, inventario, políticas, persistencia,
  eventos, dashboard y operaciones.
- **Plano de datos:** nftables, routing, NAT, interfaces y servicios de red.
- **Sensores e integraciones:** Suricata, Zeek, métricas y notificaciones.

El plano de datos debe aplicar la última política válida aunque la API o el
dashboard estén detenidos. La API puede proponer y validar cambios, pero no
debe ser una dependencia del procesamiento de paquetes.

### Recomendación inicial

1. FastAPI como interfaz administrativa, detrás de contratos Pydantic y una
   capa de servicios que no dependa del framework.
2. SQLite para la primera edición funcional, con repositorios, migraciones y
   límites explícitos; medir antes de introducir PostgreSQL.
3. nftables como backend de firewall, cargando reglas mediante transacciones
   atómicas y conjuntos/mapas cuando corresponda.
4. Kea para DHCP cuando se requiera DHCP administrado por NetOS; evitar
   implementar un servidor DHCP propio.
5. Unbound o CoreDNS según el requisito: resolver recursivo/validante frente a
   pipeline extensible de plugins. No usar DNS como barrera única de acceso.
6. Suricata y Zeek como procesos independientes y opcionales: Suricata para
   IDS/IPS y Zeek para monitorización protocolaria.
7. Dashboard TypeScript servido localmente, con un sistema visual propio y sin
   CDN en producción.

Estas son recomendaciones arquitectónicas, no decisiones de implementación
aprobadas. El rendimiento de 1 Gbps queda pendiente de benchmarks.

## 2. Investigación y referencias consultadas

Las siguientes fuentes son documentación oficial o documentación primaria:

| Fuente | Evidencia útil para NetOS |
|---|---|
| [nftables: atomic rule replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement) | `nft -f` permite reemplazar el ruleset atómicamente; evita estados parciales típicos de múltiples comandos de shell |
| [nftables: tracing](https://wiki.nftables.org/wiki-nftables/index.php/Ruleset_debug/tracing) | `nftrace` y `nft monitor trace` permiten diagnosticar el recorrido de paquetes |
| [Suricata: What is Suricata](https://docs.suricata.io/en/latest/what-is-suricata.html) | Motor de IDS, IPS y Network Security Monitoring; debe tratarse como integración |
| [Zeek: About and architecture](https://docs.zeek.org/en/current/about/index.html) | Plataforma de monitorización orientada a eventos, analizadores y logs estructurados |
| [FastAPI: OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) | La seguridad se declara en dependencias de rutas; recomienda hashing de contraseñas y tokens con expiración |
| [CoreDNS: plugin chains](https://coredns.io/manual/plugins/) | Cadena ordenada de plugins con procesamiento, fallthrough y observación de respuestas |
| [Unbound documentation](https://nlnetlabs.nl/documentation/unbound/) | Resolver recursivo y cacheado con documentación de configuración y validación |
| [Kea Administrator Reference Manual](https://kea.readthedocs.io/en/latest/) | DHCPv4/v6, API, hooks, bases de datos y ejecución con cuenta no root |
| [Cockpit documentation](https://cockpit-project.org/documentation.html) | Referencia de administración web de servidores Linux y separación de operaciones |
| [Grafana documentation](https://grafana.com/docs/grafana/latest/dashboards/) | Patrones de dashboards, paneles, variables y exploración temporal |
| [OPNsense documentation](https://docs.opnsense.org/) | Referencia de producto para administración de firewall, servicios, plugins y auditoría |
| [OpenNDS documentation](https://opennds.readthedocs.io/) | Referencia de portal cautivo; útil para comparar onboarding con enforcement de firewall |
| [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131) | Protocolo DHCPv4 |
| [RFC 8415](https://www.rfc-editor.org/rfc/rfc8415) | DHCPv6 |
| [RFC 7858](https://www.rfc-editor.org/rfc/rfc7858) | DNS sobre TLS |
| [RFC 8484](https://www.rfc-editor.org/rfc/rfc8484) | DNS sobre HTTPS |

### Clasificación de afirmaciones

- **Documentado:** comportamiento descrito por las fuentes enlazadas.
- **Recomendación:** conclusión de diseño de este documento.
- **Pendiente de verificar:** requiere prueba en Ubuntu Server, namespaces de
  red, medición de rendimiento o revisión de la versión concreta.

## 3. Comparativa de tecnologías

### 3.1 Firewall

| Alternativa | Ventajas | Limitaciones | Decisión propuesta |
|---|---|---|---|
| nftables directo | Transacciones, sets/maps, IPv4/IPv6, modelo actual del kernel | Requiere diseñar lifecycle, rollback y privilegios | **Backend principal** |
| firewalld | Zonas, D-Bus, integración de distribución | Capa adicional y semántica que puede ocultar el ruleset | Adaptador futuro opcional |
| iptables | Disponible en sistemas antiguos | Modelo legado, actualizaciones menos adecuadas para estado declarativo | No usar en el diseño nuevo |

nftables permite cargar un fichero completo de forma atómica; esta propiedad
es importante para no dejar el gateway en un estado parcialmente actualizado.
La observabilidad debe usar contadores y tracing selectivo, no tracing global.

### 3.2 DNS

| Alternativa | Ventajas | Limitaciones | Decisión propuesta |
|---|---|---|---|
| Unbound | Resolver recursivo/cacheado, validación DNSSEC y configuración madura | Menos orientado a una cadena de plugins de aplicación | Preferido para resolver local |
| CoreDNS | Cadena de plugins, extensibilidad, métricas y fallthrough | Algunas capacidades requieren plugins/build/configuración | Preferido si se necesita pipeline extensible |
| DNS propio en Python | Control total del flujo | Alto riesgo de errores de protocolo, evasión y rendimiento | No recomendado |

DNS será un servicio de red, no el mecanismo de autorización. DoH, DoT,
IPv6 y resolvers alternativos deben considerarse en la política de firewall.

### 3.3 DHCP

| Alternativa | Ventajas | Limitaciones | Decisión propuesta |
|---|---|---|---|
| Kea | DHCPv4/v6, API, hooks, backends y documentación de operación | Servicio adicional y configuración propia | Preferido para modo gateway |
| dnsmasq | Ligero y sencillo en despliegues pequeños | Menor separación de responsabilidades y extensibilidad | Puede ser perfil mínimo |
| Implementación propia | Control local | No justificada; alto riesgo operativo | No implementar |

La selección final debe considerar paquetes Ubuntu, soporte DHCPv6, reservas,
persistencia de leases y requisitos de alta disponibilidad.

### 3.4 IDS/IPS y observabilidad

| Herramienta | Rol | Dependencia de NetOS |
|---|---|---|
| Suricata | IDS/IPS y alertas basadas en reglas | Adaptador de configuración, health y eventos |
| Zeek | Metadata protocolaria, logs y scripting de monitorización | Adaptador de ingestión y retención |
| NetOS | Correlación operativa y políticas | No reemplaza analizadores maduros |

Suricata puede actuar como IDS o IPS, pero el modo inline requiere un diseño de
fallo y capacidad de procesamiento separado. Zeek es principalmente pasivo:
sus logs no deben confundirse con enforcement.

### 3.5 API y persistencia

FastAPI es adecuado como borde HTTP/WebSocket, pero la lógica de dominio debe
residir en servicios independientes del framework. SQLAlchemy/Alembic son
candidatos si la complejidad de repositorios y migraciones lo justifica;
SQLite de la biblioteca estándar puede servir para el primer núcleo, siempre
que se aísle el acceso y se midan bloqueos.

No se introducen Redis, PostgreSQL, Kafka o Celery por defecto. Se justificarían
solo con una medición o requisito concreto: múltiples nodos, colas durables
de alto volumen, retención superior o concurrencia que SQLite no pueda sostener.

## 4. Arquitectura general propuesta

```text
                         Plano de control
  Dashboard / CLI / automatización
                 |
                 v
       API versionada + contratos
                 |
   +-------------+------------------+
   |             |                  |
 Identidad    Inventario        Políticas
   |             |                  |
   +-------------+------------------+
                 |
          Persistencia + eventos
                 |
                 v
       Orquestador de aplicación
                 |
                 v
          Adaptadores privilegiados
                 |
                 v
                         Plano de datos
 Interfaces -> gateway -> nftables -> kernel
      |           |          |
     DHCP        DNS       conntrack/NAT

 Sensores externos: Suricata / Zeek -> eventos -> observabilidad
```

### Modos operativos

#### Gateway/firewall

NetOS gestiona interfaces asignadas, forwarding, NAT, DHCP, DNS y políticas.
La aplicación de políticas se realiza mediante un adaptador nftables y no por
el dashboard.

#### Monitorización

NetOS observa interfaces y eventos sin activar routing, NAT ni enforcement.
El modelo de datos y la API deben poder ejecutarse en este modo sin asumir que
NetOS es el gateway.

## 5. Componentes, interfaces y fallos

| Módulo | Responsabilidad | Interfaz pública | Dependencias permitidas | Fallo |
|---|---|---|---|---|
| `api` | HTTP/WebSocket, versionado y errores | DTOs, endpoints y health | identidad, servicios de aplicación | Error explícito; no cambia políticas por sí solo |
| `identity` | Usuarios, roles, sesiones y auth | `authenticate`, `authorize`, `revoke` | persistencia, observabilidad | Denegar por defecto; auditar |
| `inventory` | Dispositivos, interfaces y leases | repositorios/eventos de inventario | fuentes de sistema, persistencia | Mantener último estado con freshness |
| `persistence` | Migraciones y repositorios | interfaces de repositorio | driver DB | No devolver éxito si commit falla |
| `policies` | Modelo y evaluación | `compile`, `validate`, `diff` | identidad, inventario | No aplicar política inválida |
| `firewall` | Adaptador nftables | `plan`, `apply`, `rollback`, `status` | subprocess/API restringida, observabilidad | Conservar última política válida |
| `gateway` | Interfaces, rutas y NAT | plan declarativo de gateway | adaptadores OS | Preflight y rollback antes de cambios |
| `dns` | Configurar/observar resolver | lifecycle y health | Unbound/CoreDNS | Degradación explícita; no abrir acceso |
| `dhcp` | Configurar leases y reservas | lifecycle y estado | Kea/dnsmasq elegido | No perder configuración anterior |
| `events` | Eventos internos y entrega | contrato versionado | persistencia, sockets/IPC | Backpressure y reintento |
| `captive_portal` | Onboarding opcional | sesiones de portal | identidad, políticas, API | No sustituye firewall |
| `observability` | Logs, métricas y auditoría | exporters y health | OpenTelemetry/stdlib futuro | Nunca ocultar fallos críticos |
| `ids_ips` | Integrar sensores | estado, alertas, acciones | Suricata/Zeek | Fail-open/closed por política aprobada |
| `notifications` | Telegram/email/webhook futuro | adaptadores de entrega | events, secretos | Reintento limitado y DLQ futura |
| `dashboard` | Presentación y operación | API pública versionada | `api` únicamente | No afecta plano de datos |
| `lifecycle` | Instalación, actualización y servicios | preflight/apply/rollback | systemd, OS adapters | Confirmación y recuperación |

Las dependencias deben apuntar hacia contratos de dominio, nunca desde
`persistence` o `firewall` hacia el dashboard.

## 6. API y contratos

### Propuesta

- Prefijo `/api/v1`.
- JSON con identificadores estables, timestamps UTC y versiones de contrato.
- OpenAPI generado desde modelos, revisado como interfaz pública.
- Errores uniformes con código estable, mensaje seguro y correlación.
- Paginación por cursor para eventos/conexiones; límite y offset solo para
  consultas pequeñas y justificadas.
- Idempotency keys para operaciones de aplicación de configuración.
- `ETag`/versión de recurso para evitar sobrescrituras concurrentes.
- Health separado en liveness, readiness y estado degradado.

### Recursos iniciales

```text
/api/v1/auth
/api/v1/users
/api/v1/roles
/api/v1/devices
/api/v1/interfaces
/api/v1/segments
/api/v1/policies
/api/v1/firewall
/api/v1/connections
/api/v1/dns
/api/v1/events
/api/v1/audit
/api/v1/services
/api/v1/ids
/api/v1/notifications
```

No deben exponerse directamente los comandos `nft`, `ip`, `kea` o `suricata`
como API pública.

## 7. Identidad, autenticación, sesiones, usuarios y roles

### Flujo propuesto

```text
Cliente -> login MFA/opcional -> verificación de hash
        -> sesión corta + refresh/revocación
        -> autorización por recurso y acción
        -> auditoría de resultado
```

Recomendaciones:

- Hash de contraseñas con Argon2id mediante una biblioteca mantenida; soportar
  bcrypt solo como migración si aparece una base antigua.
- Cookies `HttpOnly`, `Secure` cuando exista HTTPS y `SameSite` adecuado, o
  Authorization Bearer para clientes no navegador.
- CSRF explícito para operaciones autenticadas por cookie.
- Expiración absoluta, expiración por inactividad, revocación y rotación.
- No guardar secretos en `pyproject.toml`, repositorio ni logs.
- Roles iniciales: `viewer`, `operator`, `policy-admin`, `security-admin`,
  `system-admin`, con separación de funciones.
- Las operaciones de aplicar políticas requieren permiso específico y
  preflight; leer estado no debe conceder capacidad de cambio.

La autenticación administrativa no debe confundirse con la identidad de un
dispositivo de red. El binding entre sesión de usuario, dispositivo, IP y MAC
debe ser un concepto de política explícito.

## 8. Inventario y modelo de datos

### Entidades iniciales

```text
User(id, username, status, created_at, updated_at)
Role(id, name)
UserRole(user_id, role_id)
Session(id, user_id, issued_at, expires_at, revoked_at, client_metadata)

Device(id, stable_identity, mac, hostname, vendor, first_seen, last_seen)
DeviceAddress(id, device_id, address, family, valid_from, valid_to)
Interface(id, name, ifindex, role, admin_state, oper_state)
Segment(id, name, vlan_id, address_family, cidr, mode)

Policy(id, version, status, scope, document, created_by, created_at)
PolicyDeployment(id, policy_id, generation, status, applied_at, error)

Connection(id/event_key, observed_at, device_id, protocol, endpoints, bytes)
DnsQuery(id, observed_at, device_id, qname, qtype, result, source)
SecurityAlert(id, observed_at, sensor, signature, severity, state)
AuditEvent(id, observed_at, actor, action, resource, result, correlation_id)
```

### Relaciones y reglas

- Un dispositivo puede tener varias direcciones históricas.
- Una dirección no debe sobrescribir el historial.
- Una política desplegada debe referenciar una generación inmutable.
- Los eventos de auditoría son append-only para el rol administrativo normal.
- La retención de conexiones, DNS y alertas debe ser configurable y separada
  de la retención de configuración.
- Los índices se definirán desde consultas medidas: identidad, timestamps,
  estado, segmento y correlación.

## 9. Modelo de políticas y roles

Una política debe ser declarativa y compilable, por ejemplo:

```text
scope: segment/device/group
family: ipv4/ipv6/both
direction: input/output/forward
match: source/destination/protocol/ports/identity
action: accept/drop/reject/log/mark
priority: integer
schedule: optional
```

Pipeline:

```text
documento -> validación -> normalización -> conflictos
          -> plan/diff -> preflight -> compilación
          -> aplicación atómica -> health -> commit de estado
```

El usuario no debe editar reglas kernel directamente. El compilador debe
producir un plan auditable y no modificar nada si detecta ambigüedad, conflicto
o pérdida de conectividad administrativa.

## 10. Diseño del firewall nftables

### Tablas y responsabilidades propuestas

El namespacing exacto queda pendiente de prueba, pero se recomienda una tabla
propia de NetOS por familia o una estrategia equivalente que no destruya
reglas de terceros:

- cadenas base de input/forward/output;
- cadenas de prerouting/postrouting para NAT;
- sets/mapas para dispositivos, segmentos y puertos;
- contadores por política;
- marcas solo cuando exista una razón de routing o correlación.

### Aplicación segura

1. Leer estado actual y comprobar ownership.
2. Construir un ruleset completo desde la generación candidata.
3. Validar sintaxis y dependencias sin aplicar.
4. Verificar que la administración mantendrá conectividad.
5. Cargar la generación mediante operación atómica.
6. Comprobar counters, hooks y rutas de salud.
7. Registrar la generación aplicada.
8. Rollback a la última generación válida ante fallo.

La documentación de nftables describe la sustitución atómica mediante `nft -f`.
El adaptador no debe concatenar comandos de shell no validados.

### Política de fallo

- Si falla API/dashboard: conservar reglas.
- Si falla compilación: no tocar reglas.
- Si falla aplicación: conservar última generación válida y alertar.
- Si se pierde health del gateway: ejecutar rollback seguro previamente
  preparado, no un `flush ruleset` indiscriminado.
- La estrategia fail-open/fail-closed para IDS/IPS requiere aprobación por
  segmento y función.

## 11. Gateway, routing y servicios de red

### Gateway

El módulo gateway debe planear, no improvisar, cambios de:

- selección de interfaces WAN/LAN;
- forwarding IPv4/IPv6;
- rutas y gateways;
- NAT/MASQUERADE;
- MTU y estado de enlace;
- segmentos y VLAN;
- conectividad de administración.

Cada operación de riesgo necesita:

1. snapshot;
2. preflight;
3. ventana de confirmación;
4. aplicación;
5. prueba de conectividad;
6. rollback automático si no se confirma.

### DNS

El resolver debe ser un proceso independiente, local y observable. La política
de acceso a Internet debe vivir en nftables; la redirección DNS solo ayuda al
onboarding o a una política explícita. Deben tratarse IPv4/IPv6, TCP/UDP,
DNSSEC, DoT y DoH como decisiones separadas.

### DHCP

En modo gateway se recomienda DHCPv4 y DHCPv6 mediante un servicio maduro y
configurable. Las reservas deben correlacionarse con inventario, pero el
servidor DHCP no debe depender del dashboard para continuar entregando leases.

## 12. Eventos y comunicación entre procesos

Se propone un contrato de eventos versionado:

```text
event_id, event_type, schema_version, occurred_at, producer,
subject, payload, correlation_id
```

Primera implementación posible: SQLite append-only más una cola IPC local
controlada. La selección final entre Unix socket, polling durable o broker
externo depende del volumen medido.

Requisitos:

- no perder eventos de auditoría;
- diferenciar eventos de estado y eventos de seguridad;
- backpressure;
- reintentos limitados;
- deduplicación;
- no bloquear el plano de datos por un consumidor lento.

## 13. Portal cautivo

El portal es un mecanismo opcional de onboarding, no el firewall. Debe:

- integrarse con identidad y políticas;
- declarar claramente qué segmento y dispositivo autoriza;
- soportar expiración y revocación;
- no confiar solo en una MAC;
- tener rutas de detección específicas por plataforma solo como ayuda;
- funcionar sin dejar el sistema en `allow all` si el portal falla.

OpenNDS es una referencia de arquitectura para portales cautivos; NetOS debe
reutilizar conceptos y no copiar implementación.

## 14. Observabilidad, IDS/IPS y notificaciones

### Observabilidad

- Logs estructurados en JSON, sin secretos.
- Correlation ID en API, eventos, despliegues y auditoría.
- Métricas de aplicación, nftables, interfaces, DNS, DHCP y sensores.
- Health checks diferenciados por proceso y por capacidad.
- Retención configurable.

### Suricata

Suricata debe ejecutarse como sensor/servicio independiente. NetOS gestiona
configuración declarativa, lifecycle, salud y recepción de alertas. IDS pasivo e
IPS inline deben ser perfiles diferentes con pruebas y política de fallo propia.

### Zeek

Zeek debe integrarse como fuente de logs y eventos protocolarios. Sus datos
requieren retención, normalización, control de volumen y privacidad. No debe
aplicarse una alerta de Zeek directamente como DROP sin una política aprobada.

### Notificaciones

Las notificaciones consumen eventos ya autorizados. Cada adaptador necesita
timeouts, reintentos, redacción de secretos y estado de entrega. Telegram,
webhooks o email son integraciones posteriores, no dependencias del core.

## 15. Diseño del dashboard y sistema visual

### Navegación propuesta

Barra lateral:

1. Overview
2. Gateway
3. Interfaces y segmentos
4. Dispositivos
5. Políticas de firewall
6. Conexiones y DNS
7. Alertas / IDS/IPS
8. Eventos y auditoría
9. Servicios
10. Usuarios y roles
11. Configuración / mantenimiento

### Patrones

- Resumen con estado y severidad, no solo números.
- Tablas con filtros, orden, paginación y exportación controlada.
- Vista de dispositivo con identidad, direcciones históricas, políticas,
  conexiones y alertas relacionadas.
- Vista de política con documento, diff, preflight, generación y rollback.
- Actualizaciones en tiempo real para eventos, pero polling tolerante para
  estado no crítico.
- Responsive desde 1280 px hasta tablet; accesibilidad de teclado y contraste.
- Tema claro y oscuro con tokens de diseño, no colores ad hoc.

### Sistema visual propuesto

- tipografía local;
- escala de espaciado de 4/8 px;
- colores semánticos para estado y severidad;
- componentes de tabla, badge, card, modal de confirmación y timeline;
- textos de error accionables;
- recursos empaquetados localmente, sin CDN.

Grafana aporta patrones de paneles y exploración temporal; Cockpit aporta
densidad de administración de servidor; OPNsense aporta organización de
servicios y políticas. La implementación final debe ser original y adaptada a
los contratos de NetOS.

## 16. Seguridad y separación de privilegios

### Propuesta de procesos

- `netos-api`: usuario sin privilegios; API y dashboard.
- `netos-control`: usuario sin privilegios; evaluación y persistencia.
- `netos-firewall`: adaptador mínimo con capacidades estrictamente necesarias.
- `netos-dns` / `netos-dhcp`: usuarios y capacidades propias del servicio.
- `netos-sensor-*`: cuentas separadas para Suricata y Zeek.

La forma exacta de capabilities, seccomp, namespaces y sandboxing debe validarse
en Ubuntu Server. Ningún servicio debe recibir root por comodidad.

### Secretos

- permisos de archivos mínimos;
- secret store del sistema o mecanismo de instalación protegido;
- no pasar secretos por argumentos;
- redacción de logs;
- rotación y revocación;
- backup cifrado de configuración sensible.

### Recuperación

- snapshots de configuración;
- generaciones de políticas inmutables;
- test de rollback;
- último ruleset válido persistido;
- watchdog de conectividad administrativa;
- procedimiento manual documentado si falla el propio gestor.

## 17. Estrategia de persistencia

SQLite es una opción razonable para el primer nodo local porque reduce
operación, pero no debe tratarse como cola distribuida ni como almacén
ilimitado de conexiones. Requisitos:

- migraciones versionadas;
- transacciones cortas;
- WAL evaluado mediante benchmark;
- busy timeout y errores observables;
- índices basados en consultas;
- separación entre configuración, inventario, eventos y telemetría;
- limpieza por retención;
- backup consistente y prueba de restore.

Migrar a PostgreSQL solo si se verifica una necesidad: múltiples escritores
intensos, despliegue multi-nodo, consultas analíticas o retención que exceda el
perfil local.

## 18. Rendimiento y benchmarks

No existe evidencia para prometer 1 Gbps en el hardware HP Compaq 6200 Pro,
i5-2400 y 12 GB de RAM. El resultado depende de NIC, kernel, conntrack,
reglas, tamaño de paquetes, NAT y sensores.

### Matriz de pruebas

| Escenario | Métricas |
|---|---|
| Routing sin firewall | throughput, pps, latencia, pérdida |
| NAT | throughput, CPU, pps |
| nftables con conntrack | throughput, reglas, estados, CPU |
| Sets/maps pequeños y grandes | lookup, reload, memoria |
| 1/100/1000/5000 dispositivos | memoria, tiempo de evaluación |
| Conexiones simultáneas | tasa de establecimiento, estados, RAM |
| DNS local | qps, p95/p99, cache hit, SERVFAIL |
| Suricata IDS | throughput, drops, CPU/RAM |
| Suricata IPS | throughput, latencia, drops, fail mode |
| Zeek | eventos/s, logs, CPU/RAM |
| Dashboard/API | latencia, concurrencia, WebSocket, DB locks |

### Método

- namespaces de red y tráfico reproducible;
- `iperf3`, `netperf` o equivalente aprobado;
- perfiles con MTU, tamaños de paquete y número de flujos documentados;
- repetir cada escenario y registrar versión de kernel, nft, NIC y reglas;
- separar métricas de plano de datos y plano de control;
- probar con y sin sensores.

Los benchmarks de laboratorio no equivalen automáticamente a rendimiento de
producción. El criterio de aceptación debe aprobarse antes de optimizar.

## 19. Estrategia de pruebas

### Unitarias

- modelos de identidad, roles y políticas;
- validación de contratos;
- compilador nftables sin aplicar;
- migraciones y repositorios;
- correlación de eventos;
- parser de configuración;
- redacción de secretos.

### Integración

- API con base temporal;
- login, revocación, CSRF y autorización;
- despliegue simulado de una generación de ruleset;
- adaptadores Kea/CoreDNS/Unbound simulados;
- IPC y backpressure;
- recepción de alertas Suricata/Zeek.

### Sistema

- namespaces para routing, NAT y firewall;
- reinicio de servicios;
- pérdida de API;
- reglas corruptas;
- rollback;
- cambio de interfaz;
- dual-stack;
- DNS alternativo;
- portal cautivo por segmento.

### Seguridad

- fuzzing de contratos y paquetes de integración;
- pruebas de permisos y capabilities;
- XSS/CSRF;
- replay y expiración de sesiones;
- inyección de configuración;
- DoS de conexiones y eventos;
- revisión de dependencias con SBOM y scanner aprobado.

No se ejecutarán pruebas destructivas sobre la red real.

## 20. Riesgos y limitaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Perder conectividad al aplicar reglas | Alto | Preflight, confirmación, rollback y canal de recuperación |
| SQLite insuficiente | Medio/alto | Métricas, migraciones y umbral claro para PostgreSQL |
| IPv6 no cubierto | Alto | Decisión explícita y tests dual-stack |
| DoH/DoT evade portal | Alto | Firewall como enforcement; DNS solo como onboarding |
| IPS consume CPU | Alto | Perfil opcional, benchmark y política de fail mode |
| Privilegios excesivos | Alto | Usuarios/capabilities separados |
| Sensores generan demasiado volumen | Medio | Retención, sampling, backpressure y límites |
| Cambios de distribución | Medio | OS adapters y matriz de compatibilidad |
| Dashboard se convierte en dependencia | Alto | Contratos API y plano de datos independiente |
| Carga de reglas no compatible | Medio | Detección de versión, preflight y rollback |

## 21. Decisiones que requieren aprobación

1. ¿La primera entrega habilita gateway, monitorización o ambos?
2. ¿Se soportará IPv6 desde la primera versión?
3. ¿La política por defecto será fail-closed, fail-open o por segmento?
4. ¿Se selecciona Kea o se permite un perfil dnsmasq mínimo?
5. ¿Se selecciona Unbound o CoreDNS como resolver inicial?
6. ¿SQLite queda limitado a un nodo local?
7. ¿Se exige HTTPS con certificados gestionados por NetOS?
8. ¿Qué roles administrativos son obligatorios?
9. ¿Suricata empieza como IDS o también como IPS?
10. ¿Qué retención y privacidad se aplican a Zeek, DNS y conexiones?
11. ¿Qué interfaces y topologías soportará el primer instalador?
12. ¿Qué umbral medido define “soporta 1 Gbps”?
13. ¿Se permite un canal de recuperación fuera de banda para cambios de red?
14. ¿Qué integraciones de notificación entran en la primera versión?

## 22. Plan de implementación por fases

### Fase 2 — Fundamentos de dominio

Contratos, configuración, errores, identidad, roles, repositorios, migraciones,
eventos y pruebas unitarias. Sin aplicar cambios a la red.

### Fase 3 — Inventario y observabilidad local

Interfaces, dispositivos, estado, health, logs y auditoría en modo
monitorización. Validar persistencia y retención.

### Fase 4 — Compilador y simulador de políticas

Modelo declarativo, diff, preflight y compilación nftables sin aplicación.
Tests con fixtures y namespaces simulados.

### Fase 5 — Adaptador nftables y gateway controlado

Aplicación atómica, rollback, routing/NAT y health checks en laboratorio
aislado. Requiere aprobación explícita antes de tocar cualquier host real.

### Fase 6 — DHCP, DNS y portal opcional

Integrar el servicio elegido, reservas, segmentos, onboarding y políticas.
Validar IPv4/IPv6 y evasiones DNS.

### Fase 7 — Suricata, Zeek y dashboard

Sensores opcionales, eventos, vistas administrativas, sistema visual y
notificaciones.

### Fase 8 — Instalación y certificación

Unidades systemd endurecidas, upgrade/rollback, matriz Ubuntu, documentación
operativa y benchmarks reproducibles.

## 23. Referencias y justificación de uso futuro

Las URLs y su utilidad están registradas también en
[docs/references.md](references.md). Antes de cada implementación se debe
revisar la documentación de la versión concreta instalada y registrar cambios
relevantes en una decisión técnica.

