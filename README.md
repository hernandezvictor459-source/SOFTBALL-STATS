# Softball Stats — versión inicial

## Requisitos
- Python 3.10 o superior
- pip

## Instalación
```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Instala dependencias:
```bash
pip install -r requirements.txt
```

## Ejecutar
```bash
streamlit run app.py
```

La aplicación abrirá en el navegador. La base de datos `softball_stats.db`
se crea automáticamente en la misma carpeta.

## Orden recomendado de uso
1. En "Equipos y jugadores", crea los dos equipos.
2. Registra los jugadores de cada equipo.
3. En "Crear partido", selecciona visitante, local, fecha y entradas.
4. En "Anotar jugadas", selecciona el equipo que batea y registra cada jugada.
5. Consulta el historial y las estadísticas.

## Importante sobre esta primera versión
Esta es una base funcional para comenzar. Cada registro representa una jugada/turno
y permite guardar carreras, CE, bases robadas y outs. La anotación avanzada completa
requiere una segunda etapa para modelar corredores en base, outs por jugada,
orden al bate, cambios defensivos, lanzamientos, errores y reglas específicas
de la liga. El AVG mostrado es referencial y debe revisarse al ampliar los tipos
de jugada y las reglas de turnos oficiales de tu liga.

Haz copias de seguridad periódicas del archivo `softball_stats.db`.
