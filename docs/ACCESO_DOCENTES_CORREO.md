# Acceso temporal para docentes

Al crear un usuario con rol Docente, el servidor genera una contraseña aleatoria de 24 caracteres, guarda únicamente su hash bcrypt y envía la contraseña por SMTP con TLS. No se devuelve la contraseña al administrador. Vence a las 24 horas (fechas UTC) y solo permite consultar la identidad y establecer una contraseña nueva antes de acceder a los módulos. La contraseña definitiva requiere al menos 12 caracteres y como máximo 72 bytes UTF-8.

Cambiar la contraseña o reenviar el acceso incrementa la versión de credenciales e invalida las sesiones anteriores. El reenvío está disponible para administradores cuando el usuario está activo y tiene cambio pendiente. Si el envío falla, se revierte el registro o la renovación; la contraseña anterior se conserva en un reenvío fallido. El proveedor puede aceptar un mensaje sin entregarlo inmediatamente: el aviso de éxito confirma aceptación SMTP, no llegada al buzón. Revisar spam.

Los usuarios existentes conservan sus contraseñas. El alta de otros roles conserva la contraseña manual. Los destinatarios pueden utilizar Gmail, Outlook u otros dominios: no tienen que coincidir con el proveedor remitente.

## Configurar Gmail

El archivo privado `backend/.mail.json` está excluido de Git y ya tiene los valores de servidor de Gmail. Completar localmente:

- `SMTP_USER`: dirección completa de la cuenta remitente.
- `SMTP_FROM`: la misma dirección, o un remitente autorizado por el proveedor.
- `SMTP_PASSWORD`: contraseña de aplicación de Google, sin espacios.
- `SMTP_HOST`: `smtp.gmail.com`.
- `SMTP_PORT`: `587` y `SMTP_SECURITY`: `starttls` (alternativamente 465 y `ssl`).
- `APP_URL`: dirección desde la que los docentes abrirán el sistema, sin `/login` al final. `http://localhost:5173` solo funciona en la computadora que ejecuta el proyecto; sustituirlo por una dirección accesible para ellos antes de invitarlos desde otros equipos.

Google requiere verificación en dos pasos para crear contraseñas de aplicación y algunas cuentas no permiten esta opción. Consultar https://support.google.com/mail/answer/185833?hl=es . No utilizar la contraseña habitual de la cuenta ni guardarla en el frontend. La configuración se lee en cada envío, por lo que no necesita reinicio al completar el archivo.

## Otros proveedores

Cambiar host, puerto y credenciales según el proveedor. Este adaptador admite SMTP con autenticación usuario/contraseña y TLS; no implementa OAuth2. Una cuenta que exija OAuth2 requiere otro adaptador de autenticación. Las variables de entorno con los mismos nombres tienen prioridad sobre el archivo local.

## Instalación y comprobación

Ejecutar `python migrate_temporary_password.py` desde backend para agregar los tres campos de usuarios; es repetible y no cambia contraseñas existentes. Las instalaciones nuevas los incluyen en modelos y `database_schema.sql`. Reiniciar el backend tras actualizar código.

Verificación: `python -m unittest test_temporary_password test_database_v2.DatabaseV2Tests.test_database_structure test_database_v2.DatabaseV2Tests.test_user_permissions_and_existing_tokens -v` y `npm run build` desde frontend. Las pruebas usan transacciones revertidas y correo simulado: no envían mensajes externos. El envío real queda pendiente de completar la cuenta remitente.

El envío es síncrono y sucede después de validar la inserción, antes de confirmar la transacción. SMTP y MySQL no comparten una transacción: una interrupción después de la aceptación SMTP y antes de confirmar MySQL puede producir un correo con acceso no válido. Ante una respuesta incierta, revisar la lista y reenviar si el usuario existe, o repetir el alta si no existe. Para despliegues con mayor volumen conviene incorporar una cola durable de entrega y reintentos.
