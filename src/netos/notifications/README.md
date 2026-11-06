# Notificaciones internas

Este módulo convierte algunos eventos reales del monitor en notificaciones
persistentes de control-plane. No implementa Telegram, correo, SMS, webhooks ni
otros canales externos.

## Reglas actuales

- `interface_disappeared` genera una notificación `warning`.
- `source_error` genera una notificación `warning`.
- Los demás eventos actuales no generan notificaciones porque no aportan una
  condición de alerta suficientemente definida.

La clave de deduplicación persistente combina `event_type`, `resource` y
`description`. Por tanto, el mismo evento lógico solo crea una notificación
una vez durante la vida de la base de datos. Una descripción distinta produce
una clave distinta. No se inventan alertas de intrusión, tráfico, conectividad
ni aparición de dispositivos.

## API

- `GET /api/v1/notifications?is_read=false&severity=warning&limit=100`
- `GET /api/v1/notifications/{notification_id}`
- `PATCH /api/v1/notifications/{notification_id}/read`

La API actual no exige autenticación; las notificaciones son una función
interna del control-plane local. Marcar como leída es idempotente.

La migración SQLite 5 crea `notifications` e índices por fecha, lectura y
severidad. El servicio usa el callback existente de `EventStore`; los errores
de SQLite se registran y no detienen el monitor. El callback no crea eventos
de monitorización, evitando ciclos.
