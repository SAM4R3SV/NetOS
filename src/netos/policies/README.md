# Políticas administrativas

Este módulo valida, almacena, consulta, actualiza y elimina políticas de red.
`enabled` solo expresa el estado administrativo guardado en SQLite; no activa
reglas del sistema operativo.

Las políticas requieren nombre, prioridad, dirección, acción y protocolo.
CIDR/IP se normalizan a redes, los puertos aceptan valores entre 1 y 65535 y
se rechazan puertos para `any` e `icmp`. Los nombres son únicos sin distinguir
mayúsculas y minúsculas.

Endpoints bajo `/api/v1/policies`:

- `GET /policies`
- `GET /policies/{policy_id}`
- `POST /policies`
- `PUT /policies/{policy_id}`
- `DELETE /policies/{policy_id}`

Ejemplo de creación:

```json
{
  "name": "allow-web",
  "description": "HTTP and HTTPS",
  "enabled": true,
  "priority": 100,
  "direction": "inbound",
  "action": "allow",
  "protocol": "tcp",
  "source_cidr": "192.168.1.0/24",
  "destination_cidr": "10.0.0.10",
  "destination_port": 443
}
```

La fase actual no aplica políticas a nftables, iptables ni ningún otro
componente del sistema operativo.
