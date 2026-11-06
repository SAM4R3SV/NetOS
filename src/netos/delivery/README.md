# Delivery Engine

El Delivery Engine mantiene una cola durable de trabajos de entrega hacia
proveedores genéricos. `notifications` sigue representando hechos/alertas
internos; `delivery_jobs` representa intentos hacia un destino externo. Esta
fase no implementa Telegram, Discord, webhooks, correo ni ningún proveedor
real.

## Estados

```text
pending -> sending -> sent
                  \-> retry -> sending
                  \-> failed
```

Un worker único reclama trabajos mediante una transacción SQLite y los marca
`sending` antes de invocar el proveedor. Los trabajos `sending` cuyo timestamp
supera el timeout se recuperan como `retry` durante el arranque. Los intentos
están limitados y usan backoff exponencial acotado; `retry_after_seconds` del
resultado del proveedor se respeta hasta el máximo configurado.

## Provider adapter

Los proveedores implementan el protocolo `DeliveryProvider.send(job)` y
devuelven `DeliveryResult`. El engine solo conoce éxito, fallo reintentable,
estado HTTP opcional, `retry-after` opcional y un código de error sanitizado.
Los errores de un proveedor se aíslan del worker y de otros proveedores.

La API interna `enqueue()` recibe un destino lógico y un payload JSON. Los
payloads se validan, tienen un límite de tamaño y rechazan campos que parezcan
tokens, contraseñas, cookies, secretos, autorizaciones o API keys. Los secretos
no se guardan en SQLite ni en logs; futuros adapters deberán resolverlos desde
`SecretManager` durante el envío.

No existe endpoint HTTP para crear, borrar, reintentar o enviar jobs. No se
crean jobs automáticamente para todas las notificaciones, porque todavía no
hay providers configurados.
