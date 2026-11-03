# Núcleo implementado de Fase 2.1

La implementación actual es únicamente el plano de control local:

```text
Settings -> FastAPI -> application boundary -> SQLite repositories
                         |
                         +-> structured rotating logs
```

`Database` controla conexiones cortas y migraciones versionadas. Los
repositorios solo almacenan estado de control y auditoría acotada; no existe
un almacén de telemetría ilimitada. La auditoría se purga al iniciar el
servicio según `NETOS_AUDIT_RETENTION_DAYS`, independientemente de la rotación
de logs. FastAPI se compone mediante `create_app`,
lo que permite pruebas con una base temporal sin iniciar un servidor externo.

La API escucha en `127.0.0.1` por defecto y expone únicamente salud, versión,
estado y configuración no sensible. No hay endpoints de administración, shell,
subprocess, reconciler, policy-applier ni adaptadores de red.

## Copias de seguridad

Las copias de la base deben hacerse deteniendo cambios administrativos o usando
la herramienta de backup consistente de SQLite en una futura utilidad operativa.
No se debe copiar únicamente un archivo SQLite mientras haya una operación de
escritura activa. Una restauración se realiza primero en una ruta temporal y se
verifica con `Database.initialize()` antes de sustituir la base de producción.
