# NetOS — Fase 1.2: decisiones arquitectónicas cerradas

**Fecha:** 2026-11-02  
**Plataforma objetivo:** Ubuntu Server 24.04 LTS  
**Hardware de referencia:** HP Compaq 6200 Pro SFF, Intel i5-2400,
12 GB DDR3, HDD SATA de 500 GB  
**Estado:** decisiones de diseño del MVP; la implementación requiere una
aprobación posterior explícita.

Este documento cierra el diseño mínimo para construir un MVP pequeño,
verificable y seguro. No instala dependencias, no configura el sistema y no
autoriza cambios sobre la red real.

## 1. Decisiones resumidas

| ID | Decisión | Estado |
|---|---|---|
| D-101 | El MVP tendrá perfiles `monitor` y `gateway-lab` separados | Adoptada |
| D-102 | `monitor` no modifica tráfico, interfaces, rutas ni servicios de red | Adoptada |
| D-103 | `gateway-lab` exige activación explícita y preflight satisfactorio | Adoptada |
| D-104 | Un único reconciler será autoridad de aplicación del plano de datos | Adoptada |
| D-105 | Solo `policy-applier` podrá modificar nftables | Adoptada |
| D-106 | API y applier se comunicarán por Unix socket local versionado | Adoptada |
| D-107 | SQLite se limitará a estado del control-plane y auditoría acotada | Adoptada |
| D-108 | Telemetría de alta cardinalidad se conservará en logs rotados o backend futuro | Adoptada |
| D-109 | La identidad de dispositivo será una entidad con evidencias, confianza y expiración | Adoptada |
| D-110 | RBAC de NetOS será independiente de usuarios Unix y capabilities | Adoptada |
| D-111 | El último ruleset válido será un artefacto versionado restaurable sin FastAPI | Adoptada |
| D-112 | El MVP no incluirá portal cautivo, Zeek ni Suricata IPS | Adoptada |
| D-113 | IPv6 se modelará desde el inicio, pero no se activará en el gateway MVP | Adoptada |
| D-114 | El dashboard inicial tendrá cuatro áreas operativas | Adoptada |
| D-115 | No se prometerá 1 Gbps sin benchmark reproducible | Adoptada |

## 2. Alcance del modo `monitor`

### Responsabilidad

El modo `monitor` observa el host y las redes visibles sin convertirse en
gateway. Puede recopilar:

- interfaces y su estado;
- direcciones y rutas observables;
- dispositivos y evidencias detectadas;
- eventos de servicios;
- métricas locales;
- logs de sensores externos cuando estén instalados.

### Prohibiciones

En `monitor`, NetOS no debe:

- modificar paquetes;
- activar forwarding;
- instalar NAT;
- cambiar rutas;
- escribir configuración Netplan;
- iniciar o reconfigurar DHCP/DNS de la red;
- aplicar reglas nftables de enforcement;
- alterar interfaces, bridges o VLAN;
- ejecutar comandos privilegiados desde la API.

Un adaptador de lectura puede consultar estado del sistema si la instalación
le concede el acceso mínimo necesario, pero toda operación de escritura debe
rechazarse por diseño.

### Condiciones de salida

El modo monitor se considera terminado cuando puede inventariar y observar en
un entorno de laboratorio, demuestra ausencia de mutaciones y mantiene
funcionalidad aunque el dashboard se detenga.

## 3. Activación y condiciones de `gateway-lab`

`gateway-lab` no será un modo implícito. Requiere:

1. activación explícita en configuración local;
2. confirmación del operador;
3. preflight exitoso;
4. dos interfaces físicas claramente identificadas, o dos namespaces/veth
   de laboratorio;
5. una interfaz LAN y una WAN sin solapamiento de subredes;
6. ownership explícito de DHCP, DNS, routing y nftables;
7. canal de administración identificado y protegido;
8. snapshot del estado previo;
9. ruleset inicial generado y validado sin aplicar;
10. procedimiento de rollback disponible.

El preflight debe fallar si detecta:

- una sola interfaz para un escenario que requiera routing;
- DHCP externo no identificado en el segmento administrado;
- solapamiento de CIDR;
- ausencia de acceso de recuperación;
- reglas de terceros cuyo ownership no pueda determinarse;
- versión o capacidades incompatibles;
- configuración IPv6 no definida.

El gateway MVP será IPv4. IPv6 tendrá representación de datos, validación y
criterios de prueba, pero no se habilitará como plano de forwarding hasta que
se apruebe una política IPv6 completa.

## 4. Reconciler y `policy-applier`

### Responsabilidades

El reconciler es el único orquestador que convierte un estado deseado en un
estado aplicado. Su flujo es:

```text
intención versionada
        |
        v
validación de esquema y autorización
        |
        v
normalización y detección de conflictos
        |
        v
preflight de interfaces, rutas y ownership
        |
        v
compilación a generación declarativa
        |
        v
validación sintáctica sin aplicar
        |
        v
policy-applier
        |
        v
aplicación atómica + health check
        |
        +--> éxito: generación aplicada
        |
        +--> fallo: rollback a última generación válida
```

### Autoridad única

- La API crea intenciones y consulta estado.
- El reconciler decide si una intención es aplicable.
- El `policy-applier` es el único componente autorizado a escribir nftables.
- Ningún módulo del dashboard, API, inventario, gateway o sensor invoca
  directamente `nft`.
- El applier no acepta comandos arbitrarios; recibe una generación declarativa
  validada y limitada por el contrato.

### Generaciones

Cada aplicación tiene:

- `generation_id`;
- hash del documento normalizado;
- timestamp UTC;
- actor;
- preflight;
- estado `planned`, `applying`, `applied`, `failed` o `rolled_back`;
- referencia al artefacto;
- generación anterior válida.

La API no debe informar `applied` antes de recibir confirmación del applier.

## 5. Comunicación API–proceso privilegiado

Se adopta un Unix socket local con:

- propietario y permisos restrictivos;
- protocolo versionado;
- mensajes estructurados;
- identificador de correlación;
- timeout;
- respuesta explícita de preflight, apply y rollback;
- rechazo de operaciones no incluidas en la interfaz;
- límites de tamaño y frecuencia.

La API se ejecuta sin privilegios. El applier tendrá únicamente los permisos
del sistema necesarios para su función, definidos durante la implementación y
verificados en Ubuntu Server 24.04 LTS.

No se utilizará `sudo` parametrizado, shell concatenado ni una API genérica de
comandos. D-Bus puede evaluarse posteriormente, pero no es requisito del MVP.

## 6. Persistencia y límites de SQLite

SQLite será el almacén local del control-plane para:

- configuración normalizada;
- usuarios, sesiones y roles;
- inventario pequeño;
- intenciones y generaciones;
- estado de aplicación;
- auditoría administrativa acotada;
- migraciones.

No se usará SQLite como almacén ilimitado de:

- paquetes;
- conexiones de alta cardinalidad;
- consultas DNS sin límites;
- logs completos de Zeek;
- eventos de Suricata de larga retención;
- métricas de alta frecuencia.

### Reglas operativas

- WAL solo después de validar el patrón de acceso en laboratorio.
- Un escritor lógico para cambios de control.
- Transacciones cortas.
- `busy_timeout` y errores visibles.
- Migraciones versionadas y reversibles cuando sea posible.
- Backups consistentes y prueba de restore.
- Cuotas de tamaño y retención.
- No alojar la base en filesystem de red.

La documentación oficial de [SQLite WAL](https://www.sqlite.org/wal.html)
confirma que lectores y escritores pueden coexistir en muchos casos, pero que
solo hay un escritor simultáneo y existen checkpointing y ficheros auxiliares.

## 7. Logs, telemetría y retención

### Categorías

1. **Auditoría:** cambios administrativos, autenticación, policy apply y
   rollback. Persistencia durable y retención configurable.
2. **Operación:** lifecycle, health, errores y estado de servicios. Logs
   estructurados rotados.
3. **Telemetría:** conexiones, DNS, métricas y eventos de sensores. Logs
   estructurados rotados, con límites de volumen.
4. **Diagnóstico:** tracing selectivo y temporal; nunca habilitado globalmente
   por defecto.

Cada registro debe incluir timestamp UTC, componente, severidad,
`correlation_id` cuando exista y una versión de esquema. Nunca se almacenan
contraseñas, tokens ni secretos.

Retención inicial propuesta:

- auditoría: 90 días o cuota definida por el operador;
- operación: 14 días;
- telemetría: 24 horas localmente en MVP;
- diagnóstico: solo durante la ventana de soporte.

Estos valores son defaults de diseño y deben ser configurables, no resultados
de una prueba de capacidad.

## 8. Identidad de dispositivos

Un dispositivo no se identifica únicamente por IP o MAC. El modelo usa una
entidad lógica y un conjunto de evidencias:

```text
DeviceIdentity
  stable_id
  evidence[]

Evidence
  kind: mac | ipv4 | ipv6 | dhcp_lease | hostname | interface | authenticated
  value
  source
  confidence
  observed_at
  expires_at
```

### Reglas

- Cambiar de IP no crea automáticamente un dispositivo nuevo.
- Una MAC aleatoria no se fusiona automáticamente con una identidad anterior.
- Una dirección IPv6 temporal se registra como evidencia con expiración.
- El hostname DHCP es evidencia, no identidad fuerte.
- La correlación puede sugerir continuidad, pero debe conservar incertidumbre.
- Las políticas de acceso se asignan a identidad, segmento y contexto, no a
  una IP que se supone permanente.
- El inventario debe permitir múltiples direcciones simultáneas.

[RFC 8981](https://www.rfc-editor.org/rfc/rfc8981) documenta que los hosts
pueden generar direcciones IPv6 temporales con identificadores aleatorios y
cambiantes; por ello no se debe diseñar un binding rígido a una sola dirección.

## 9. Autenticación, autorización y privilegios

### NetOS

El MVP tendrá autenticación administrativa y autorización por acción:

- `viewer`: lectura de estado no sensible;
- `operator`: operaciones operativas no destructivas;
- `policy-admin`: crear, validar y solicitar aplicación de políticas;
- `security-admin`: alertas, auditoría de seguridad y sensores;
- `system-admin`: lifecycle y configuración operativa aprobada.

Los nombres son roles de NetOS, no usuarios Unix.

### Sistema operativo

El proceso API, el reconciler y los adaptadores se ejecutan con identidades
Unix separadas. Las capabilities, sandboxing y acceso a sockets son controles
del sistema operativo, no permisos concedidos por el RBAC HTTP.

Un `system-admin` de NetOS no obtiene automáticamente root. El applier solo
ejecuta operaciones previamente definidas y validadas.

### Sesiones

- expiración absoluta e inactividad;
- revocación;
- cookies seguras para navegador o Bearer para clientes no navegador;
- CSRF si se usan cookies para mutaciones;
- auditoría de éxito y fallo;
- no exponer tokens en logs o URLs.

## 10. Recuperación y último ruleset válido

El ruleset aplicado se almacena como artefacto versionado independiente de la
base de datos:

```text
state/
  desired/
  applied/
  last-known-good/
  metadata/
```

Cada artefacto contiene generación, hash, versión de esquema y metadatos de
preflight. El directorio y sus permisos se definirán en la implementación.

### Arranque

Un servicio de restauración independiente de FastAPI:

1. verifica el artefacto;
2. verifica versión y ownership;
3. verifica interfaces requeridas;
4. carga la última generación válida;
5. ejecuta health checks;
6. deja el sistema en estado `ready` o `degraded`.

### Fallo durante aplicación

- No hacer `flush ruleset` como recuperación genérica.
- Conservar la generación anterior si la nueva falla.
- Registrar `failed` y el motivo.
- Reintentar solo con límite y backoff.
- Requerir intervención para conflictos de ownership.
- Mantener canal de recuperación documentado.

La sustitución atómica de nftables reduce estados parciales, pero no sustituye
este lifecycle. La operación se apoyará en [nftables atomic replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement)
y tracing selectivo documentado en [nftables tracing](https://wiki.nftables.org/wiki-nftables/index.php/Ruleset_debug/tracing).

## 11. Instalación, desinstalación y recuperación

### Instalación

La instalación futura será explícita e idempotente:

1. preflight de Ubuntu Server 24.04 LTS;
2. validación de hardware, interfaces y espacio;
3. creación de usuarios y directorios;
4. instalación de artefactos versionados;
5. generación de configuración sin secretos en argumentos;
6. validación estática;
7. activación del perfil `monitor`;
8. gateway solo mediante activación posterior.

El instalador no debe cambiar la red automáticamente sin una operación de
gateway confirmada.

### Desinstalación

- detener primero servicios de NetOS;
- conservar configuración y auditoría por defecto;
- retirar solo recursos con ownership NetOS;
- no eliminar reglas de terceros;
- ofrecer exportación y backup;
- verificar que no quedan unidades, sockets ni procesos propios.

### Recuperación

Debe existir un procedimiento documentado para:

- volver a `monitor`;
- restaurar el último ruleset;
- desactivar el applier;
- recuperar acceso administrativo;
- restaurar SQLite y artefactos;
- dejar intactos servicios de terceros.

## 12. Pruebas y laboratorio

### Unitarias

- validación de configuración;
- modelo de evidencias de dispositivos;
- roles y autorización;
- normalización de políticas;
- detección de conflictos;
- generación de IDs y hashes;
- serialización de mensajes IPC;
- estados de apply y rollback;
- migraciones.

### Integración

- API con repositorios temporales;
- API–socket–applier con applier simulado;
- persistencia de generaciones;
- errores y timeouts;
- autenticación, CSRF y revocación;
- recuperación después de reinicio.

### Laboratorio de red

Namespaces/veth o hardware aislado:

- monitor no modifica tráfico;
- gateway IPv4 enruta solo con activación;
- NAT y forwarding;
- cliente no autorizado;
- actualización de política;
- rollback;
- caída de API;
- caída del applier;
- reinicio del host;
- discrepancia de interfaces;
- pruebas IPv6 de observación, sin activar forwarding en MVP.

No se probará contra la red real.

## 13. Métricas y criterios de hardware

No se declara soporte de 1 Gbps sin resultados reproducibles. Cada benchmark
debe registrar versión de Ubuntu/kernel/nftables, NIC, tamaño de paquetes,
número de flujos, reglas, conntrack, CPU, RAM, latencia y pérdida.

### Escenarios

1. routing IPv4 sin firewall;
2. NAT;
3. nftables con conntrack;
4. reglas con sets/maps;
5. API y applier bajo cambios de configuración;
6. DNS/DHCP del proveedor seleccionado;
7. Suricata IDS opcional;
8. Zeek opcional;
9. almacenamiento y retención en HDD.

### Criterio

El hardware se considera apto para un perfil solo si:

- no hay pérdida por saturación en el escenario objetivo;
- p95/p99 de latencia cumple el umbral aprobado;
- CPU y memoria tienen margen sostenido;
- no se acumulan errores de conntrack, disco o eventos;
- reinicios y rollback cumplen sus tiempos de aceptación.

Los umbrales exactos requieren aprobación y medición; no se inventan en esta
fase.

## 14. Dependencias y condiciones de reconsideración

| Decisión | Dependencias | Reconsiderar si |
|---|---|---|
| IPv4 gateway MVP | dos interfaces/lab, nftables, routing | se exige IPv6 operativo o bridge transparente |
| SQLite control-plane | un nodo, baja escritura, retención acotada | múltiples escritores, HA o telemetría alta |
| Unix socket | un host, applier local | se requiere control multi-host |
| sin IDS/IPS MVP | hardware modesto, foco en control | benchmark demuestra margen y requisito operativo |
| sin portal MVP | políticas base aún en validación | onboarding sea requisito de aceptación |
| logs rotados | retención local corta | se requiere búsqueda histórica amplia |
| un proveedor DNS/DHCP | topología simple | aparecen múltiples segmentos o DHCPv6 obligatorio |

## 15. Fuentes consultadas

Consultadas el **2026-11-02**:

- [SQLite WAL](https://www.sqlite.org/wal.html): único escritor,
  checkpointing, ficheros auxiliares y límites de WAL.
- [nftables atomic replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement):
  carga atómica de rulesets.
- [nftables tracing](https://wiki.nftables.org/wiki-nftables/index.php/Ruleset_debug/tracing):
  diagnóstico selectivo.
- [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html):
  lifecycle y readiness de servicios.
- [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html):
  sandboxing, capabilities y directorios aislados.
- [RFC 8981](https://www.rfc-editor.org/rfc/rfc8981):
  direcciones IPv6 temporales.
- [Ubuntu network configuration](https://ubuntu.com/server/docs/explanation/networking/configuring-networks/):
  configuración de red de Ubuntu Server.
- [Suricata AF_PACKET](https://docs.suricata.io/en/latest/capture-hardware/af-packet.html):
  captura Linux; no aporta un benchmark del hardware objetivo.
- [Zeek architecture](https://docs.zeek.org/en/current/about/architecture.html):
  pipeline de eventos y análisis protocolario.

