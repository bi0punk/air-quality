# Informe de fusión

## Decisión de diseño

Se tomó **FastAPI + SQLite** como base principal, porque el segundo proyecto ya tenía:

- mejor modelo de persistencia,
- mejor extensibilidad,
- mejor API,
- dashboard ya funcional.

Sobre esa base se incorporó lo valioso del primer proyecto:

- compatibilidad con el payload `POST /data`,
- soporte para `voltaje`,
- soporte para `calidad_aire`,
- importación del CSV existente.

## Qué se conservó de cada uno

### Del proyecto Flask + CSV
- formato simple de ingestión
- datos `valor_analogico`, `voltaje`, `calidad_aire`
- simpleza de integración con ESP32 / Arduino

### Del proyecto FastAPI + SQLite
- API moderna
- dashboard web
- almacenamiento estructurado
- estadísticas y consulta histórica

## Qué se eliminó o corrigió

- IP hardcodeada del proyecto Flask
- almacenamiento sólo en CSV como mecanismo principal
- separación artificial entre dos modelos incompatibles
- falta de migración de datos antiguos
- esquema sin `voltage` ni `quality_label`

## Resultado

Un único proyecto, con un backend coherente, migración de legados, visualización web y compatibilidad con ambos formatos de carga.
