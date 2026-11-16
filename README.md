# Backend Advance ICI

API Django REST Framework para expedientes, actas, documentos y cuentas.

## Iniciar en Windows con PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py cargar_demo --password 123456
.\.venv\Scripts\python.exe manage.py runserver
```

Si `py` no está disponible, usar `python -m venv .venv`. Si `.venv` ya existe, comenzar en la instalación de dependencias.

Abrir `http://127.0.0.1:8000/api/`. Iniciar sesión en `http://127.0.0.1:8000/api-auth/login/` con usuario `root` y clave `123456`. `cargar_demo` prepara las cuentas y tres expedientes ficticios solo en la base local.

## Rutas principales

- `/api/expedientes/`: CRUD, filtros, búsqueda y paginación.
- `/api/actas/`: acta PDF única por expediente.
- `/api/expedientes/{id}/documentos/`: varios archivos para una ficha.
- `/api/documentos/carga-masiva/`: archivos para distintas fichas.
- `/api/cuentas/`: cuentas y roles.
- `/api/resumen/` y `/api/estado/`: resumen y estado del sistema.

## Validaciones al enviar datos manualmente

La API devuelve HTTP 400 con errores por campo. Por ejemplo, un `POST /api/actas/`
en `multipart/form-data` con `expediente=10` cuando ese expediente no existe
responde `{"expediente": ["No existe un expediente con el ID 10."]}` y no crea
el acta. La misma referencia se valida al vincular cuentas. Los campos ajenos o
de solo lectura enviados en JSON o formularios también se informan por nombre.
La carga masiva de documentos indica los ID de expedientes faltantes antes de
guardar cualquier archivo.

En Raw data de expedientes, seleccione `application/json`: una fecha debe ir
entre comillas (`"fecha_examen": "2026-11-10"`) y los valores numéricos pueden
ir sin comillas (`"anio_egreso": 2026`, `"semestre_egreso": 1`,
`"nota_examen": 6.3`). Si falta poner comillas a un valor de esos campos,
la API indica el formato esperado para ese campo. Para otros errores de sintaxis
informa que el JSON está mal formado. Si el JSON es válido pero el valor es
incorrecto, devuelve el error bajo el nombre del campo.
La misma regla de mensajes se aplica a cuentas (`rol` admite `administrador`,
`coordinador` o `estudiante`; `activo` usa `true` o `false`), al cambio de
colegiatura y al estado del sistema. Los errores de contraseñas, correo,
longitudes, duplicados y archivos se devuelven bajo el campo que debe corregir.

Para subir un acta desde `/api/actas/`, use el formulario de la API navegable:
seleccione el ID del expediente, adjunte el PDF en `archivo` y envíe el formulario.
`multipart/form-data` requiere un archivo y un separador (`boundary`) generado
por el navegador o cliente HTTP; pegar JSON en la pestaña Raw data con ese media
type produce un error de formato. Raw data de actas inicia en `application/json`
con un ejemplo de los campos editables. En ese formato puede enviar el PDF en
Base64, sin el prefijo `data:`:

```json
{"expediente": 1, "archivo_base64": "JVBERi0xLjQKLi4u"}
```

El ejemplo es ilustrativo: reemplace la cadena por el contenido completo de un
PDF real. En PowerShell puede obtenerlo con
`[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\ruta\acta.pdf"))`.
Una URL en `archivo` no sustituye al PDF adjunto. `id`,
`nombre_original`, `fecha_carga` y `cargada_por` son campos de solo lectura.
Cuando el expediente ya tiene acta, debe editar la existente con `PATCH` o `PUT`
en `/api/actas/{id}/`, no crear otra con `POST`. Para reemplazarla desde Raw data,
seleccione `application/json` y envíe `{"archivo_base64": "..."}` con `PATCH`.

En `/api/documentos/carga-masiva/`, Raw data también inicia en
`application/json` con esta estructura:

```json
{
  "archivos": [
    {"expediente": 1, "nombre": "informe.pdf", "contenido_base64": "BASE64_DEL_PRIMER_ARCHIVO"},
    {"expediente": 2, "nombre": "foto.jpg", "contenido_base64": "BASE64_DEL_SEGUNDO_ARCHIVO"}
  ]
}
```

Cada elemento indica su propio expediente de destino. Se admiten de 1 a 20
archivos; el cuerpo JSON completo debe ser menor de 14 MB. Los archivos grandes
o lotes mayores pueden enviarse con el formulario multipart. La API comprueba
todos los ID, nombres, Base64 y contenidos antes de guardar el lote.

## Revisión del frontend y catálogos

El frontend ubicado en `../AdvanceICI` usa Firebase Authentication, Firestore y
Supabase Storage; actualmente no consume esta API Django ni comparte su base de
datos. Para integrarlo en EV3 se necesita sustituir sus servicios de datos,
autenticación y archivos, además de adaptar los nombres de campos, los ID
(cadenas en Firestore, enteros aquí), los roles y la nota decimal con coma de la
interfaz al formato de la API.

La tabla del panel y del buscador es una sola tabla de expedientes compartida.
Sus datos corresponden a `Expediente` y `Acta`. El historial visible en la ficha
corresponde a `CambioColegiatura`; la auditoría corresponde a `RegistroAuditoria`.
Este backend además registra `PerfilUsuario`, `DocumentoExpediente` y
`ConfiguracionSistema`. Todos estos modelos ya están registrados en Django Admin.

No hay edificios ni categorías en los formularios o datos actuales del proyecto.
Semestre, estado de colegiatura y rol son opciones cerradas con significado en
las reglas de negocio; agregarlas libremente desde Admin requeriría cambiar esas
reglas y el frontend. Si se incorpora un catálogo real en el futuro, entonces
corresponde crear su modelo, registrar su administración y exponer sus opciones
en la API antes de agregar el selector a la interfaz.


