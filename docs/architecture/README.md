# Arquitectura propuesta

## Principios

1. **Separación de planos:** la API, el dashboard y las integraciones operan
   en el plano de control; las políticas compiladas y aplicadas al kernel
   pertenecen al plano de datos.
2. **Independencia del dashboard:** el plano de datos no depende de la
   disponibilidad, versión o tecnología del dashboard.
3. **Adaptadores explícitos:** nftables, interfaces, DHCP, DNS e IDS/IPS se
   integran detrás de interfaces propias de NetOS.
4. **Persistencia controlada:** el acceso a la base de datos se concentra en
   `persistence`; los módulos de dominio no ejecutan SQL ad hoc.
5. **Fallos observables:** los errores de seguridad, persistencia y aplicación
   de políticas deben quedar registrados y no convertirse en éxitos falsos.
6. **Portabilidad Linux:** Ubuntu Server es la primera plataforma; las
   diferencias entre distribuciones deben aislarse en adaptadores y lifecycle.

## Módulos

| Directorio | Responsabilidad |
|---|---|
| `api` | API administrativa y contratos externos |
| `identity` | Usuarios, autenticación, sesiones y autorización |
| `inventory` | Dispositivos, interfaces y fuentes de descubrimiento |
| `persistence` | Esquema, migraciones y repositorios |
| `policies` | Modelo, evaluación y compilación de políticas |
| `firewall` | Adaptador de nftables y estado aplicado |
| `gateway` | Routing, NAT y gestión de interfaces |
| `dns` | Servicio y configuración DNS |
| `dhcp` | Servicio y configuración DHCP |
| `events` | Eventos internos, entrega y retención |
| `captive_portal` | Onboarding y portal cautivo opcional |
| `observability` | Logs, métricas, health checks y auditoría |
| `ids_ips` | Integraciones opcionales de IDS/IPS |
| `notifications` | Integraciones de notificación |

## Flujo de control

```text
API / CLI / automatización
            |
            v
Identidad -> Políticas -> Persistencia de estado
                         |
                         v
              Adaptador nftables
                         |
                         v
                    Kernel Linux
```

El dashboard y las notificaciones consumen contratos del plano de control. No
aplican directamente reglas de red.

## Flujo del plano de datos

```text
Interfaces Linux -> Gateway -> nftables
         |             |
         v             v
       DHCP          DNS
         |
         v
     Inventario -> Eventos -> Observabilidad
```

Este diagrama es una propuesta de límites, no una indicación de que los
servicios ya estén implementados o configurados.

