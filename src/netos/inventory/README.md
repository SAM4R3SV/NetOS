# Inventario persistente

El inventario conserva dispositivos observados por fuentes pasivas del
monitor, actualmente la caché ARP local disponible en Linux. Una observación
no es un escaneo ni demuestra que el dispositivo siga conectado.

La MAC válida y normalizada (`aa:bb:cc:dd:ee:ff`) es la identidad estable.
Observaciones repetidas actualizan `last_seen`, `last_ip` y `last_interface`,
pero conservan `first_seen`. Una IP compartida o reasignada no fusiona
dispositivos: la deduplicación nunca se basa solo en IP.

Las observaciones sin MAC válida se descartan para no crear identidades
falsas. No se inventan hostname ni fabricante; esos campos permanecen vacíos
hasta que exista una fuente fiable. Los registros no se eliminan por dejar de
aparecer en ARP.

## API

- `GET /api/v1/inventory`: lista los dispositivos persistidos.
- `GET /api/v1/inventory/{device_id}`: consulta un dispositivo.
- `PATCH /api/v1/inventory/{device_id}`: modifica únicamente
  `display_name`.

Ejemplo:

```json
{
  "display_name": "Impresora oficina"
}
```

`first_seen`, `last_seen`, MAC, IP, interfaz, estado y demás datos de
observación no pueden modificarse mediante el endpoint administrativo.

La persistencia se ejecuta mediante la infraestructura SQLite común y una
falla de persistencia se registra como evento del monitor sin detener la
recolección. El inventario no realiza consultas externas, descubrimiento
activo, ping ni cambios de red.
