# Referencias técnicas de NetOS

Este índice conserva fuentes primarias para revisar las decisiones del
proyecto. Las referencias no implican que la tecnología esté aprobada para
integración.

## Plano de datos y firewall

- [nftables wiki — atomic rule replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement):
  base para cargas atómicas y rollback.
- [nftables wiki — ruleset tracing](https://wiki.nftables.org/wiki-nftables/index.php/Ruleset_debug/tracing):
  diagnóstico selectivo con `nftrace`.
- [Linux nftables project](https://www.netfilter.org/projects/nftables/index.html):
  contexto del proyecto y documentación primaria.
- [firewalld documentation](https://firewalld.org/documentation/):
  alternativa de gestión de firewall orientada a zonas y servicios.
- [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html):
  lifecycle, readiness y tipos de servicio para separar el applier del API.
- [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html):
  sandboxing, capabilities y directorios de estado por servicio.

## Gateway, DNS y DHCP

- [CoreDNS plugin manual](https://coredns.io/manual/plugins/):
  cadenas de plugins, fallthrough y observación de respuestas.
- [Unbound documentation](https://nlnetlabs.nl/documentation/unbound/):
  resolver recursivo, cacheado y validación.
- [Kea Administrator Reference Manual](https://kea.readthedocs.io/en/latest/):
  DHCPv4/DHCPv6, hooks, APIs y operación.
- [Ubuntu Server network configuration](https://ubuntu.com/server/docs/explanation/networking/configuring-networks/):
  Netplan y la capa de configuración de red de Ubuntu Server.
- [RFC 2131 — DHCPv4](https://www.rfc-editor.org/rfc/rfc2131).
- [RFC 8415 — DHCPv6](https://www.rfc-editor.org/rfc/rfc8415).
- [RFC 7858 — DNS over TLS](https://www.rfc-editor.org/rfc/rfc7858).
- [RFC 8484 — DNS over HTTPS](https://www.rfc-editor.org/rfc/rfc8484).

## Seguridad de red

- [Suricata documentation](https://docs.suricata.io/en/latest/):
  IDS, IPS, NSM, modos de captura y operación.
- [Suricata AF_PACKET](https://docs.suricata.io/en/latest/capture-hardware/af-packet.html):
  captura Linux y configuración de AF_PACKET; no constituye un benchmark para
  el hardware de NetOS.
- [Zeek documentation](https://docs.zeek.org/en/current/):
  arquitectura, analizadores, scripting y logs.
- [Zeek architecture](https://docs.zeek.org/en/current/about/architecture.html):
  separación entre event engine y script interpreter.
- [OpenNDS documentation](https://opennds.readthedocs.io/):
  referencia de portal cautivo y onboarding.

## API, persistencia y administración

- [FastAPI security documentation](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/):
  autenticación, hashing y expiración de tokens.
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/):
  contratos y lifecycle de WebSocket.
- [Pydantic documentation](https://docs.pydantic.dev/latest/):
  validación y serialización de contratos.
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/):
  alternativa de capa de persistencia.
- [Alembic documentation](https://alembic.sqlalchemy.org/):
  migraciones versionadas.
- [Cockpit documentation](https://cockpit-project.org/documentation.html):
  referencia de administración web de Linux.
- [Grafana dashboard documentation](https://grafana.com/docs/grafana/latest/dashboards/):
  patrones de paneles, variables y exploración temporal.
- [OPNsense documentation](https://docs.opnsense.org/):
  referencia de organización de administración de firewall.
- [SQLite WAL](https://www.sqlite.org/wal.html):
  concurrencia, único escritor, checkpointing y restricciones de WAL.

## Estándares y operación

- [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html):
  usuarios, capabilities, sandboxing y ejecución de servicios.
- [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html):
  lifecycle, dependencias y reinicio.
- [Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html):
  referencia de privilegios dividibles.
- [RFC 8981 — IPv6 temporary addresses](https://www.rfc-editor.org/rfc/rfc8981):
  direcciones temporales y sus implicaciones para identidad y seguimiento.

## Regla de actualización

Antes de adoptar una versión concreta se comprobarán:

1. documentación de esa versión;
2. compatibilidad con Ubuntu Server objetivo;
3. advisories de seguridad;
4. requisitos de CPU/RAM;
5. procedimiento de rollback;
6. pruebas reproducibles en laboratorio.

## Fecha de revisión

Estas referencias fueron consultadas para la revisión arquitectónica Fase 1.1
el **2026-11-02**. Las páginas de documentación evolucionan; antes de
implementar debe verificarse la versión concreta disponible en Ubuntu Server.
