# Usar el sistema en otro equipo

GitHub conserva el código y el esquema SQL, pero no los registros de MySQL. localhost siempre apunta al equipo donde se ejecuta el servicio.

## Continuar con los mismos datos

1. En MySQL Workbench del equipo original, usar Server > Data Export. Seleccionar alerta_temprana_v2 y exportar estructura y datos a un archivo SQL privado.
2. Guardar ese respaldo fuera de GitHub: incluye cuentas y hashes de contraseñas, además de los registros escolares. Los archivos de backups/ están excluidos de Git.
3. En el otro equipo instalar MySQL 8, Python 3.12 y Node.js; clonar el repositorio y restaurar el archivo mediante Server > Data Import.
4. Configurar backend/.database-url con las credenciales de MySQL del nuevo equipo. No copiar una conexión suponiendo que la contraseña local será la misma.
5. Instalar dependencias y arrancar backend y frontend según README.md. La clave JWT local se genera nuevamente, por lo que será necesario iniciar sesión otra vez.

No ejecutar el esquema vacío ni repetir el seed sobre el respaldo restaurado: ya contiene los registros. Cada equipo tendrá una copia independiente; los cambios no se sincronizan al hacer git push.

## Comenzar con una base vacía

Ejecutar database_schema_actual.sql en un esquema nuevo y vacío. Este archivo reúne las 28 tablas actuales y no necesita aplicar los antiguos ajustes SQL de contexto. Se debe crear de forma segura un administrador con contraseña hasheada y configurar la gestión 2026 con su calendario antes de ejecutar seeds/seed_150_estudiantes_matriculas.sql. No se incluyen credenciales iniciales.

El seed crea 150 estudiantes ficticios y sus matrículas SIMULADO, 25 por grado de primero a sexto A. Reutiliza los cursos existentes, valida conflictos y toma la fecha inicial del calendario. Necesita permisos para crear temporalmente una rutina. No agrega asistencia, notas, materias ni asignaciones docentes.

## Una base compartida entre dispositivos

Para trabajar sobre los mismos registros en varios equipos se necesita alojar el backend y MySQL en un servidor accesible con controles de acceso. Eso aún no está configurado. Subir el código a GitHub no publica el sistema ni la base de datos.
