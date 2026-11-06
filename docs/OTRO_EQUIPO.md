# Usar el sistema en otro equipo

GitHub conserva el código, el esquema SQL, la documentación y la evidencia. **No** conserva los registros de MySQL, el dataset real, los artefactos del modelo ni las conexiones privadas. `localhost` siempre apunta al equipo donde se ejecuta el servicio.

## Traslado a la laptop (paquete del 6 de noviembre de 2026)

En el equipo original se preparó, **fuera de Git**, la carpeta `TRASLADO_LAPTOP_16_DE_JULIO` (en el Escritorio, también comprimida en .zip). Es **privada**: contiene la base completa (con hashes de contraseñas) y los datos escolares anonimizados. Hay que copiarla por USB o por una nube privada; nunca subirla a GitHub ni compartirla.

| En el paquete | Destino en la laptop |
|---|---|
| `base_de_datos/alerta_temprana_v2.sql` | Se restaura en MySQL (paso 3) |
| `privado/data/` | `16-DE-JULIO/data/` |
| `privado/backend/artifacts/` | `16-DE-JULIO/backend/artifacts/` (modelo XGBoost y reportes de métricas) |
| `privado/backend/data/` | `16-DE-JULIO/backend/data/` |
| `privado/seeds_sin_git/*.sql` | `16-DE-JULIO/seeds/` |
| `RESUMEN_PARA_CHAT.md` | Raíz de `16-DE-JULIO/` (resumen para Claude en el chat) |
| `claude_memoria/*.md` | Memoria de Claude Code (paso 7, opcional) |

### Pasos

1. **Instalar** en la laptop: MySQL Server 8.0 (Workbench opcional), Python 3.12, Node.js 20 o superior y Git.
2. **Clonar** el repositorio y cambiar a la rama de trabajo:
   ```powershell
   git clone https://github.com/krixthian/16-DE-JULIO.git
   cd 16-DE-JULIO
   git checkout actividades-15-19-modulos
   ```
3. **Restaurar la base** (crea `alerta_temprana_v2` con sus 28 tablas y todos los registros). En PowerShell, con el usuario de MySQL de la laptop:
   ```powershell
   & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p --default-character-set=utf8mb4 -e "source RUTA\TRASLADO_LAPTOP_16_DE_JULIO\base_de_datos\alerta_temprana_v2.sql"
   ```
   También sirve Workbench: Server > Data Import > Import from Self-Contained File.
4. **Copiar los archivos privados** a las rutas de la tabla de arriba.
5. **Configurar la conexión**: crear `backend/.database-url` con una sola línea, usando el usuario y la contraseña de MySQL **de la laptop**:
   ```
   mysql+pymysql://USUARIO:CONTRASENA@localhost/alerta_temprana_v2
   ```
   La clave JWT (`backend/.jwt-secret`) se genera sola al arrancar; habrá que iniciar sesión otra vez.
6. **Instalar dependencias y comprobar**:
   ```powershell
   python -m pip install -r backend/requirements.txt
   npm --prefix frontend ci
   cd backend; python -m unittest discover -p "test_*.py"; cd ..
   npm --prefix frontend run build
   ```
   Deben pasar los 49 tests (unos 10 minutos) y el build debe terminar sin errores. Para verificar que la base restaurada es la misma:
   ```powershell
   cd backend; python -c "from sqlalchemy import inspect, text; from database import engine; i=inspect(engine); c=engine.connect(); print(len(i.get_table_names()), sum(len(i.get_foreign_keys(t)) for t in i.get_table_names()), c.execute(text('select count(*) from matriculas')).scalar(), c.execute(text('select count(*) from alertas')).scalar())"
   ```
   Debe imprimir `28 47 940 13` (o 790 matrículas si ya se ejecutó la limpieza de las simuladas).
7. **Claude Code** (opcional): `CLAUDE.md`, en la raíz del repositorio, ya trae el contexto y las reglas del proyecto. Para conservar también la memoria, copiar `claude_memoria/*.md` a `%USERPROFILE%\.claude\projects\<carpeta>\memory\`. `<carpeta>` es la ruta del proyecto en la laptop con `:` y `\` cambiados por `-` (por ejemplo `C--Users-Cristhian-Desktop-16-DE-JULIO`). Se crea al abrir Claude Code por primera vez en el proyecto.
8. **Arrancar**: backend con `python -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend` y frontend con `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173`. En el panel de Claude Code basta con la configuración de `.claude/launch.json`.

### Prueba integral sobre MySQL (opcional)

`backend/test_integral_mysql.py` necesita una base **vacía** cuyo nombre termine en `_pruebas`, creada con `database_schema_actual.sql` cambiando el nombre de la base. No forma parte del paquete: en la laptop se crea solo si se quiere repetir esa prueba (ver `docs/PLAN_PRUEBAS.md`).

No ejecutar el esquema vacío ni repetir el seed sobre el respaldo restaurado: ya contiene los registros. Cada equipo tiene una copia independiente; los cambios en la base no se sincronizan al hacer git push.

## Comenzar con una base vacía

Ejecutar `database_schema_actual.sql` en un esquema nuevo y vacío. Este archivo reúne las 28 tablas actuales y no necesita los antiguos ajustes SQL de contexto. Antes de ejecutar `seeds/seed_150_estudiantes_matriculas.sql` hay que crear de forma segura un administrador con contraseña hasheada y configurar la gestión 2026 con su calendario. No se incluyen credenciales iniciales.

El seed crea 150 estudiantes ficticios y sus matrículas SIMULADO, 25 por grado de primero a sexto A. Reutiliza los cursos existentes, valida conflictos y toma la fecha inicial del calendario. Necesita permisos para crear temporalmente una rutina. No agrega asistencia, notas, materias ni asignaciones docentes.

## Una base compartida entre dispositivos

Para trabajar sobre los mismos registros en varios equipos hay que alojar el backend y MySQL en un servidor accesible con controles de acceso. Eso aún no está configurado. Subir el código a GitHub no publica el sistema ni la base de datos.
