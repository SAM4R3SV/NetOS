# Identidad administrativa

El módulo `identity` mantiene una clasificación manual asociada a un
dispositivo existente del inventario. La identidad administrativa está
separada de la observación técnica: una categoría o un nivel `trusted` no
demuestran el tipo real del dispositivo ni equivalen a autenticación o
autorización técnica.

Cada dispositivo puede tener como máximo una clasificación. Las categorías
disponibles son `computer`, `server`, `router`, `switch`, `camera`, `iot`,
`mobile`, `printer` y `unknown`. La confianza puede ser `trusted`, `unknown` o
`restricted`. También se conservan rol, propietario, notas y fechas de
creación/actualización.

## API

- `GET /api/v1/identity`: lista clasificaciones existentes.
- `GET /api/v1/identity/{device_id}`: consulta la clasificación.
- `PUT /api/v1/identity/{device_id}`: crea o reemplaza la clasificación.
- `DELETE /api/v1/identity/{device_id}`: retira la clasificación sin borrar
  el dispositivo del inventario.

Todos los endpoints comprueban que el dispositivo exista. Un dispositivo sin
clasificación continúa apareciendo normalmente en el inventario.

La migración SQLite 4 usa `device_id` como clave primaria y referencia
`devices(id)` con `ON DELETE CASCADE`. No se realizan fingerprinting, escaneos,
consultas externas, inferencias por OUI/hostname ni cambios de red.
