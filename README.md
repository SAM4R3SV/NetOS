# NetOS

NetOS es una plataforma modular para administración, seguridad y observabilidad
de redes Linux. El nuevo proyecto se diseña para Ubuntu Server como primera
plataforma objetivo, con portabilidad futura a otras distribuciones Linux.

Esta carpeta es el proyecto nuevo y deliberadamente independiente de
`../NetOS_obsolete/`. El código antiguo se conserva únicamente como referencia
para auditoría y recuperación selectiva de ideas; no se copia ni se reutiliza
automáticamente.

## Objetivos

- Ofrecer dos modos operativos principales:
  - **Gateway/firewall:** gestión del plano de datos, routing, NAT y políticas.
  - **Monitorización:** inventario, eventos y observabilidad sin actuar como gateway.
- Separar el plano de control del plano de datos.
- Mantener las políticas de red aunque el dashboard o la API estén detenidos.
- Usar Python como lenguaje principal del backend.
- Adoptar nftables mediante un adaptador explícito, sin implementar un motor de
  paquetes propio en Python.
- Mantener una base preparada para futuras integraciones opcionales de IDS/IPS,
  notificaciones y portal cautivo.

## Estructura

```text
NetOS/
├── src/netos/             # Paquetes del backend y del plano de control
├── dashboard/             # Cliente web; separado del backend
├── installer/             # Instalación, actualización y desinstalación
├── deploy/systemd/        # Unidades y configuración de servicios
├── docs/                  # Arquitectura y decisiones aprobadas
└── tests/                 # Pruebas unitarias, integración y sistema
```

Los módulos de red todavía no están implementados. En esta fase solo se crea
la estructura inicial y se fijan límites arquitectónicos.

## Límites iniciales

- No se configuran interfaces, rutas, DNS, DHCP, NAT, nftables, iptables ni
  systemd.
- Las dependencias runtime se declaran en `pyproject.toml` y se instalan solo
  dentro de un entorno virtual.
- No se reutiliza la arquitectura del proyecto obsoleto sin una decisión
  documentada y aprobada.
- El dashboard no es una dependencia del plano de datos.

## Fase 2.1: núcleo ejecutable

El núcleo actual implementa únicamente el plano de control local:

- configuración validada mediante variables `NETOS_*`;
- SQLite para estado y auditoría acotada, con migraciones versionadas;
- API FastAPI local, enlazada a `127.0.0.1` por defecto;
- logs JSON rotados con retención predeterminada de 30 días;
- auditoría SQLite con retención independiente, también de 30 días por defecto;
- pruebas unitarias y de integración sin privilegios.

### Instalación local

En Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

En Ubuntu Server:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Copia `.env.example` a `.env` solo si necesitas personalizar valores. No
incluyas secretos en ese archivo ni en el repositorio.

### Ejecución y pruebas

```text
python -m netos.main
python -m pytest
```

La API documenta su contrato en `/docs` cuando el proceso está en ejecución.
La base se crea en `data/netos.sqlite3` y los logs en `logs/`, ambos excluidos
por `.gitignore`.

## Fase 2.2: monitorización de red de solo lectura

La monitorización obtiene datos actuales del host sin modificar interfaces,
rutas, DNS, DHCP, forwarding o firewall:

- interfaces mediante `psutil.net_if_addrs()` y `psutil.net_if_stats()`;
- contadores mediante `psutil.net_io_counters(pernic=True)`;
- índice, tipo y virtualización mediante `/sys/class/net` en Linux cuando
  están disponibles;
- vecinos IPv4 únicamente desde `/proc/net/arp` en Linux.

Las tasas de transferencia se calculan solo entre dos muestras válidas en
memoria. Los contadores reiniciados, interfaces ausentes y tiempos inválidos
no producen tasas falsas. Los eventos se mantienen en un buffer acotado en
memoria y no se almacena cada muestra en SQLite.

Endpoints:

- `GET /api/v1/network/interfaces`
- `GET /api/v1/network/interfaces/{interface_name}`
- `GET /api/v1/network/interfaces/{interface_name}/statistics`
- `GET /api/v1/network/summary`
- `GET /api/v1/network/devices`
- `GET /api/v1/network/events?limit=100`

La recolección se activa por defecto cada 5 segundos. Puede configurarse con
`NETOS_MONITORING_ENABLED`, `NETOS_MONITORING_INTERVAL_SECONDS` y
`NETOS_NETWORK_DISCOVERY_ENABLED`.

En Windows, `psutil` proporciona interfaces y contadores disponibles, pero el
lector de vecinos ARP y la identificación Linux de virtualización no se
simulan: esas fuentes devuelven vacío o desconocido. La validación real de
`/proc` y `/sys` debe ejecutarse posteriormente en Ubuntu Server.

## Fuera de esta fase

No están implementados gateway, firewall, nftables, reconciler,
policy-applier, DNS, DHCP, routing, NAT, forwarding, inventario avanzado,
autenticación de usuarios, dashboard, portal cautivo, Suricata, Zeek ni
servicios systemd. La ausencia de estos componentes es intencional: no se
realizan cambios de red ni se ejecutan comandos privilegiados.
