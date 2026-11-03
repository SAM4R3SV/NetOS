# Monitorización de red de solo lectura

## Fuentes

La adquisición está separada de FastAPI:

- `psutil.net_if_addrs()` y `psutil.net_if_stats()` para interfaces,
  direcciones, estado y MTU.
- `psutil.net_io_counters(pernic=True)` para contadores del sistema.
- `/sys/class/net/<nombre>` en Linux para índice, tipo y detección de
  interfaces virtuales cuando el kernel expone esos datos.
- `/proc/net/arp` en Linux para la caché local de vecinos IPv4.

No se ejecutan comandos, no se realizan barridos y no se leen rutas DHCP
arbitrarias. Los archivos Linux no disponibles en Windows no se sustituyen con
datos simulados.

## Ciclo de vida

`MonitorService` realiza una muestra inicial y, si está activado, ejecuta un
hilo daemon con intervalo configurable de 5 segundos por defecto. `stop()`
despierta el hilo, espera su finalización y se invoca desde el lifespan de
FastAPI.

Las estadísticas actuales, dispositivos observados y tasas permanecen en
memoria. Las tasas requieren dos muestras: si el contador disminuye por un
reinicio o la duración no es positiva, la tasa de esa interfaz se omite.

## Eventos

`EventStore` mantiene un máximo de 500 eventos en memoria y compara el último
estado de cada interfaz. Solo genera detección, desaparición, cambio de estado,
cambio de IPv4 o error de fuente cuando corresponde. No escribe una fila por
ciclo en SQLite.

## Limitaciones

La caché ARP es evidencia local, no una prueba de que el dispositivo esté
conectado actualmente. MAC, IP e identidad se exponen como observaciones con
fuente y fecha, no como identidad permanente de una persona o dispositivo.
