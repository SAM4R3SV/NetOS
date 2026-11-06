# Diseño de expansión de plataforma: DNS, DDNS, integraciones e instalador

Estado: propuesta arquitectónica, no implementación.

Este documento consolida el diseño de las capacidades posteriores a la Fase
2.7. Distingue entre comportamiento existente, diseño propuesto, trabajo
pendiente y hechos que todavía deben verificarse en el entorno de despliegue.

## 1. Resumen ejecutivo

NetOS debe conservar un núcleo local-first y tratar DNS externo, DDNS,
notificaciones externas y herramientas auxiliares como integraciones
desacopladas. El control-plane mantiene el estado deseado y la auditoría; los
adaptadores de proveedores ejecutan operaciones idempotentes; un reconciler
explícito evita que el dashboard sea la autoridad del plano de datos.

Recomendación de orden:

1. endurecer y abstraer el Secret Manager;
2. implementar un Delivery Engine genérico;
3. añadir Telegram read-only y Discord webhook;
4. crear el instalador TUI;
5. implementar DNS externo y después DNS interno;
6. implementar DDNS;
7. integrar herramientas externas;
8. añadir topología y visualización.

No se deben comenzar DNS, DDNS ni proveedores externos antes de disponer de
credenciales, delivery, auditoría y pruebas de recuperación suficientemente
estables.

## 2. Estado real del repositorio

### Existente

- Python mínimo `>=3.10`, FastAPI, SQLite y pytest.
- API local bajo `/api/v1/`.
- Configuración mediante variables `NETOS_*`.
- Monitorización read-only y `EventStore`.
- Inventario persistente, identidad administrativa y notificaciones internas.
- `SecretManager` en `src/netos/security/secrets/`.
- `deploy/systemd/` contiene únicamente `.gitkeep`; no existe una unidad
  systemd ni un usuario de servicio definido.

### Diseñado en este documento

- Interfaces de proveedores, reconciliación, delivery, DNS, DDNS, TUI y
  visualización.

### Pendiente de implementación

- Todos los módulos de DNS, DDNS, Telegram, Discord, Delivery Engine,
  instalador y topología.

### Pendiente de verificar

- Usuario Linux definitivo del servicio.
- Política de firewall y puertos del host.
- Resolver y DHCP actualmente usados por el router.
- Soporte exacto de systemd y `LoadCredential` en la imagen Ubuntu final.
- Capacidades, límites y términos de cada cuenta/proveedor que se contrate.

## 3. Arquitectura general propuesta

```text
Dashboard / CLI / TUI
          |
       API local
          |
  Control-plane y SQLite
  |        |          |
DNS state  Delivery   Audit/events
  |        |
Reconciler  Provider adapters
  |        |
CoreDNS     Telegram / Discord / future providers
```

Reglas:

- La API administra intención y estado; no contiene implementaciones de
  proveedores.
- Cada proveedor implementa una interfaz común y conserva sus particularidades
  en un adaptador.
- Los secretos se resuelven por referencia a `SecretManager`, nunca desde
  SQLite o configuración pública.
- Toda operación externa tiene timeout, resultado normalizado, auditoría sin
  secretos y límites de frecuencia.
- El monitor nunca espera indefinidamente a un proveedor externo.
- Desactivar una integración detiene sus operaciones, pero no elimina
  automáticamente sus secretos ni su configuración.

Estructura conceptual, a adaptar cuando se implemente:

```text
src/netos/
├── security/secrets/
├── notifications/
├── delivery/
├── integrations/
│   ├── base.py
│   ├── telegram/
│   ├── discord/
│   ├── dns/
│   ├── ddns/
│   └── network_tools/
├── dns/
│   ├── manager.py
│   ├── records.py
│   └── local_server/
├── installer/
└── monitoring/
```

No se deben crear repositorios paralelos para las mismas entidades ni hacer
que los adaptadores importen FastAPI.

## 4. DNS externo

### Modelo de dominio

- `DnsProvider`: adaptador, capacidades, endpoint y estado.
- `DnsZone`: proveedor, nombre, identificador externo y estado de sincronización.
- `DnsRecord`: zona, nombre, tipo, TTL, valores, identificador externo.
- `DnsCredentialRef`: solo referencia a `SecretManager`, nunca el valor.
- `DnsOperation`: operación, actor, fecha, resultado y error sanitizado.

La interfaz común debe incluir `list_zones`, `list_records`, `upsert_record`,
`delete_record` y `check_credentials`, con una matriz de capacidades para
indicar si un proveedor permite crear zonas, DNSSEC, RRsets, IPv6 o solo
registros.

El reconciler compara estado deseado y observado, usa identificadores externos
cuando existen y trata `409`, `429` y respuestas transitorias según políticas
específicas. No debe asumir que un `PUT` de un proveedor equivale a un
`PATCH` de otro.

### Proveedores candidatos

| Proveedor | Hecho verificable | Diseño recomendado | Pendiente |
|---|---|---|---|
| deSEC | API REST para dominios y RRsets; tokens con permisos; límites documentados y `429`/`Retry-After`. | Primer adaptador completo para zonas/RRsets y DDNS si la cuenta lo permite. | Confirmar capacidades y límites de la cuenta concreta. |
| Cloudflare | API de zonas y registros; tokens API con permisos por zona. | Adaptador con token restringido a DNS de zonas seleccionadas. | Confirmar permisos mínimos y límites aplicables al plan. |
| Hurricane Electric | Candidato útil para DNS/DDNS, pero las capacidades de API deben verificarse antes de diseñar operaciones. | Mantener como adaptador posterior, no bloquear el MVP. | Verificar documentación oficial vigente. |
| Dynv6 | Candidato para DDNS con IPv4/IPv6. | Adaptador DDNS separado del gestor de zonas. | Verificar protocolo, autenticación y límites. |

Fuentes oficiales consultadas: [deSEC API](https://desec.io/docs/),
[deSEC RRsets](https://desec.readthedocs.io/en/latest/dns/rrsets.html),
[deSEC tokens](https://desec.readthedocs.io/en/latest/auth/tokens.html),
[deSEC rate limits](https://desec.readthedocs.io/en/latest/rate-limits.html) y
[Cloudflare DNS records API](https://developers.cloudflare.com/api/operations/dns-records-for-a-zone-dns-record-list-dns-records).

La gestión externa debe poder desactivarse completamente sin afectar el DNS
interno ni el resto del control-plane.

## 5. DNS interno

El dominio recomendado es `home.arpa`; no debe usarse `.local` para DNS unicast
porque está reservado habitualmente para mDNS.

### Comparación

| Criterio | CoreDNS | dnsmasq |
|---|---|---|
| Arquitectura | Plugins encadenados y Corefile. | Servicio compacto con configuración simple. |
| Consumo | Bajo/moderado; depende de plugins. | Muy bajo, adecuado para hardware modesto. |
| Automatización | Buena separación por plugins y APIs externas. | Fácil para DHCP/forwarding, menos modular para control-plane complejo. |
| IPv4/IPv6 | Adecuado con plugins estándar. | Adecuado para resolución y forwarding básicos. |
| VLAN/futuro | Mejor base para vistas, zonas y plugins. | Puede servir, pero la configuración crece más rápidamente. |
| Riesgo operativo | Requiere controlar Corefile y lifecycle. | Menor superficie, pero más dependencia de configuración estática. |

Recomendación: CoreDNS para el servidor DNS interno de NetOS, administrado
como proceso externo por un adaptador y un reconciler. dnsmasq queda como
opción de instalación pequeña cuando se necesite simplicidad y DHCP integrado.
NetOS no debe convertirse en un servidor DNS escrito en Python.

Funciones previstas:

- zonas y registros A/AAAA/CNAME internos;
- upstream configurable;
- caché y forwarding;
- estado y estadísticas;
- auditoría de cambios;
- resolución local sin Internet.

El primer despliegue debe evitar competir con el router: un único servidor
escucha en una dirección/puerto explícitos, el DHCP debe anunciarlo solo si el
administrador lo autoriza y no se debe modificar el router automáticamente.
Queda pendiente decidir si NetOS será el resolver anunciado por DHCP o si el
router continuará siendo el resolver principal.

Fuentes: [CoreDNS plugins](https://coredns.io/plugins/) y
[Corefile](https://coredns.io/2017/07/23 Corefile-explained/).

## 6. DDNS

DDNS debe ser un módulo separado, aunque comparta validadores, credenciales,
rate limiting y auditoría con DNS externo.

Flujo:

1. Obtener IPv4/IPv6 desde fuentes configurables y etiquetar la fuente.
2. Rechazar direcciones privadas, CGNAT o resultados inválidos para un
   proveedor que requiera dirección pública.
3. Comparar con el estado confirmado del proveedor.
4. Actualizar solo si cambió la dirección.
5. Validar la respuesta y registrar estado, fecha y error sanitizado.
6. Aplicar backoff y frecuencia mínima.

La IP de una interfaz WAN no se debe presentar como IP pública sin verificación.
CGNAT y doble NAT pueden impedir la publicación aunque la actualización DDNS
sea correcta. DDNS nunca abre puertos, modifica firewall ni intenta evadir
CGNAT.

### NoIP.at

La búsqueda oficial realizada solo confirma la existencia del servicio en
[noip.at](https://noip.at/). No se encontró una especificación pública
verificable del endpoint, método, autenticación, parámetros, respuestas ni
frecuencia permitida. Por tanto:

- no se debe inventar una URL ni una petición;
- no se debe reutilizar automáticamente la API de No-IP.com;
- el adaptador queda pendiente de documentación oficial o confirmación del
  proveedor;
- cualquier prueba futura requiere consentimiento explícito y credenciales
  de prueba.

### Otros proveedores

DuckDNS, deSEC, Dynv6 y Cloudflare deben implementarse como adaptadores
independientes solo después de verificar sus protocolos oficiales vigentes.
No se debe asumir que un proveedor que acepta el protocolo DynDNS estándar
ofrece también gestión completa de zonas.

## 7. Telegram y Discord

### Telegram

Primera entrega:

- envío de alertas;
- estado read-only;
- consulta de notificaciones, dispositivos e interfaces.

La identidad autorizada debe ser una lista explícita de `chat_id`/usuarios
permitidos, separando `observer` y `admin`. El token del bot solo autentica al
bot ante Telegram; no concede permisos administrativos a usuarios del chat.

Para consultas se recomienda long polling inicialmente, con offset persistido
fuera de secretos y `allowed_updates` mínimo. La administración posterior debe
usar confirmaciones, autorización por usuario, auditoría y bloqueo de acciones
sensibles.

Fuentes: [Telegram Bot API](https://core.telegram.org/bots/api),
[getUpdates](https://core.telegram.org/bots/api#getupdates) y
[sendMessage](https://core.telegram.org/bots/api#sendmessage).

### Discord

La primera entrega debe ser un webhook unidireccional con filtros por
severidad y prueba de conexión bajo consentimiento. No se debe implementar un
bot completo. El webhook se guarda en Secret Manager, no en SQLite ni en
configuración pública.

El adaptador debe respetar las cabeceras de rate limit y respuestas `429`.
La URL del webhook se considera una credencial y nunca se muestra completa.

Fuente: [Discord Execute Webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook).

## 8. Delivery Engine

El motor debe ser independiente de `notifications`:

- `notifications` conserva el hecho/alerta;
- `delivery_jobs` representa intentos por proveedor y destino.

Estados: `pending`, `sending`, `sent`, `retry`, `failed`.

Campos previstos: notificación, proveedor, destino lógico, payload
sanitizado/no secreto, intentos, próximo intento, timestamps, código HTTP y
error sanitizado. Los secretos se resuelven solo durante el envío y no se
persisten en el job.

Debe incluir:

- cola SQLite durable;
- recuperación de `sending` al reiniciar;
- backoff con límite;
- rate limits por proveedor/destino;
- timeouts;
- aislamiento: un proveedor fallido no bloquea otro;
- idempotencia para evitar duplicados cuando el proveedor lo permita.

No se debe modificar retroactivamente la tabla de notificaciones de Fase 2.6
para convertirla en cola.

## 9. Network Tools externos

NetOS debe funcionar sin estas herramientas.

| Categoría | Ejemplos | Tratamiento |
|---|---|---|
| Servicio autoalojable | IT-Tools u otras utilidades web aisladas | Despliegue opcional, sin acceso implícito al control-plane. |
| Aplicación enlazada | Herramientas de diagnóstico externas | Dashboard muestra enlace/estado, no credenciales ni datos sensibles. |
| Integrable por API | Solo herramientas con API documentada y estable | Adaptador independiente tras revisión de autenticación y licencia. |
| No recomendable | Servicios sin mantenimiento, API o límites claros | No integrar en el núcleo. |

IT-Tools puede ser útil como servicio auxiliar, pero su licencia, imagen,
exposición y mantenimiento deben verificarse para la versión elegida. No se
debe asumir API por el mero hecho de que exista una interfaz web. Delphi.tools
y herramientas similares requieren la misma verificación antes de clasificarse
como dependencia.

No se deben enviar direcciones, topología, credenciales ni inventario a
servicios externos sin una decisión explícita y una política de privacidad.

## 10. Dashboard y topología

Markmap puede servir para jerarquías y documentación, pero no es adecuado como
representación primaria de una topología de red real. Se recomienda una
biblioteca de grafos con nodos, aristas, metadatos y estados explícitos.

Cada relación debe tener una procedencia:

- `verified`: evidencia directa de una fuente fiable;
- `configured`: relación declarada por el administrador;
- `inferred`: hipótesis derivada, siempre etiquetada;
- `unknown`: ausencia de evidencia.

El dashboard debe mostrar dispositivos, interfaces, DNS interno/externo, DDNS,
IP pública, historial, integraciones, delivery y herramientas disponibles.
Nunca debe dibujar conexiones físicas no verificadas.

## 11. Seguridad y Secret Manager

Todos los proveedores usan referencias a `SecretManager`, con nombres
separados por integración, por ejemplo `telegram.bot_token` o
`dns.cloudflare.zone_token`.

El gestor actual no cifra en reposo; su seguridad depende del propietario y
permisos del sistema de archivos. Riesgos pendientes:

- no hay integración con systemd credentials;
- Windows depende de ACLs NTFS y no ofrece la misma garantía que POSIX;
- no existe rotación automática ni versionado de credenciales;
- la exposición accidental del proceso/volcado de memoria no está resuelta;
- la política de backup del directorio de secretos debe definirse;
- falta una comprobación de despliegue del usuario de servicio y de ACLs.

La integración futura debe usar tokens con privilegios mínimos, permitir
desactivar proveedores sin borrar secretos y registrar solo identificadores,
hashes no reversibles o estados, nunca valores.

Systemd `LoadCredential=` es una alternativa de despliegue a evaluar: hace
disponible una credencial como archivo en un directorio privado del servicio.
La compatibilidad exacta debe verificarse en Ubuntu objetivo.

Fuente: [systemd credentials](https://systemd.io/CREDENTIALS/) y
[systemd.exec LoadCredential](https://www.freedesktop.org/software/systemd/man/systemd.exec.html).

## 12. Instalador TUI

El instalador debe ser opcional y no una dependencia de ejecución. Flujo:

1. detectar plataforma, usuario, dependencias y estado actual;
2. seleccionar componentes de forma independiente;
3. validar configuración sin escribir hasta confirmar;
4. crear o actualizar solo archivos autorizados;
5. validar credenciales con consentimiento explícito;
6. mostrar resumen;
7. permitir cancelar sin cambios parciales;
8. registrar estados `installed`, `configured`, `enabled` y `connected`.

No debe sobrescribir configuraciones sin autorización, ni crear puertos,
unidades o reglas de red sin mostrarlos y confirmarlos. Las pruebas deben usar
un root temporal y nunca `/etc`, `/var/lib` o el router real.

Después de instalar, el dashboard debe administrar integraciones mediante
operaciones de control-plane; el instalador no debe convertirse en la única
interfaz de configuración.

## 13. Roadmap revisado

### Fase 2.8 — Delivery Engine

- Objetivo: cola durable y adaptadores de entrega aislados.
- Dependencias: notificaciones 2.6, Secret Manager 2.7.
- Afecta: `delivery/`, persistencia, auditoría.
- Riesgos: duplicados, reintentos, filtrado de secretos.
- Pruebas: reinicio, `429`, timeout, backoff, recuperación de `sending`.
- Aceptación: un proveedor fallido no detiene monitorización.
- Fuera: proveedores concretos y administración remota.

### Fase 2.9 — Telegram read-only y alertas

- Dependencias: Delivery Engine y Secret Manager.
- Afecta: `integrations/telegram/`, configuración y autorización.
- Riesgos: exposición del token, autorización insuficiente.
- Aceptación: alertas y consultas solo para usuarios permitidos.
- Fuera: comandos administrativos.

### Fase 2.10 — Discord webhook

- Dependencias: Delivery Engine.
- Afecta: `integrations/discord/`.
- Riesgos: URL del webhook, rate limits.
- Aceptación: envío unidireccional, filtros y rotación documentada.
- Fuera: bot completo.

### Fase 2.11 — Telegram administración autorizada

- Dependencias: Telegram 2.9, auditoría.
- Afecta: autorización, confirmaciones, comandos.
- Riesgos: escalada de privilegios y acciones irreversibles.
- Aceptación: roles observer/admin, allowlist y confirmación.
- Fuera: acceso administrativo por conocer el token.

### Fase 2.12 — Instalador TUI

- Dependencias: contrato estable de configuración y componentes.
- Afecta: `installer/`, documentación y tests.
- Riesgos: sobrescritura, permisos y rollback.
- Aceptación: instalación cancelable, idempotente y probada en Ubuntu
  headless.
- Fuera: implementación de DNS o proveedores dentro del instalador.

### Fase 3.0 — DNS externo

- Dependencias: Secret Manager, reconciler y auditoría.
- Afecta: `dns/`, `integrations/dns/`, migraciones.
- Riesgos: operaciones destructivas, límites y permisos de tokens.
- Aceptación: deSEC y Cloudflare con dry-run, idempotencia y rollback lógico.
- Fuera: DNS interno y DDNS genérico.

### Fase 3.1 — DNS interno

- Dependencias: decisión CoreDNS/dnsmasq, instalador y puertos aprobados.
- Afecta: `dns/local_server/`, systemd y configuración.
- Riesgos: conflicto con router/DHCP y pérdida de resolución.
- Aceptación: `home.arpa`, A/AAAA/CNAME, upstream y operación sin Internet.
- Fuera: reemplazar automáticamente el DHCP del router.

### Fase 3.2 — DDNS

- Dependencias: Secret Manager, delivery/retry y DNS externo.
- Afecta: `integrations/ddns/`.
- Riesgos: CGNAT, IP falsa, frecuencia y APIs no documentadas.
- Aceptación: un proveedor verificado, IPv4/IPv6, comparación y backoff.
- Fuera: NoIP.at hasta disponer de documentación oficial.

### Fase 3.3 — Network Tools externos

- Dependencias: contrato de integración y revisión de licencias.
- Afecta: dashboard y health checks.
- Riesgos: exposición de información y dependencia operacional.
- Aceptación: herramientas opcionales, aisladas y desactivables.
- Fuera: convertirlas en módulos del núcleo.

### Fase 3.4 — Topología y dashboard de integraciones

- Dependencias: inventario, identidad, DNS y estados de proveedores.
- Afecta: dashboard, API de lectura y modelo de procedencia.
- Riesgos: inferencias presentadas como hechos.
- Aceptación: procedencia visible y relaciones no verificadas diferenciadas.
- Fuera: descubrimiento activo no aprobado.

## 14. Decisiones pendientes

1. Usuario y grupo definitivos del servicio Ubuntu.
2. CoreDNS frente a dnsmasq para el primer despliegue.
3. Si DHCP del router anunciará el DNS de NetOS.
4. Política de backup y recuperación del almacén de secretos.
5. Proveedor DNS inicial y alcance mínimo de sus tokens.
6. Fuente aprobada para descubrir IP pública.
7. Documentación oficial del protocolo de NoIP.at.
8. Biblioteca de grafos del dashboard.
9. Licencias y método de aislamiento de Network Tools.
10. Disponibilidad de `LoadCredential` en la imagen Ubuntu objetivo.

## 15. Referencias y nivel de certeza

Las capacidades de deSEC, Cloudflare, CoreDNS, Telegram, Discord y systemd
citadas arriba se basan en documentación oficial enlazada. La evaluación de
IT-Tools/Delphi.tools es preliminar y requiere revisión de la versión,
licencia y despliegue escogidos. NoIP.at no tiene, en las fuentes consultadas,
una especificación pública suficiente para diseñar una petición segura.

Este documento no implementa ninguna de las funcionalidades descritas, no
crea migraciones, no hace peticiones a proveedores y no modifica servicios de
red.
