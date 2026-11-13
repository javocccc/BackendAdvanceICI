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

Abrir `http://127.0.0.1:8000/api/`. Iniciar sesión en `http://127.0.0.1:8000/api-auth/login/` con usuario `root` y clave `123456`. `cargar_demo` prepara las cuentas y dos expedientes ficticios solo en la base local.

## Rutas principales

- `/api/expedientes/`: CRUD, filtros, búsqueda y paginación.
- `/api/actas/`: acta PDF única por expediente.
- `/api/expedientes/{id}/documentos/`: varios archivos para una ficha.
- `/api/documentos/carga-masiva/`: archivos para distintas fichas.
- `/api/cuentas/`: cuentas y roles.
- `/api/resumen/` y `/api/estado/`: resumen y estado del sistema.

Para ejecutar las pruebas:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

Para mostrar una segunda página con las tres fichas ficticias, iniciar el servidor con páginas de 2:

```powershell
$env:DJANGO_PAGE_SIZE = "2"
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir `/api/expedientes/?page=1` y `/api/expedientes/?page=2`. Sin esa variable, la API usa 20 resultados por página.

La base `db.sqlite3`, los archivos subidos en `media/` y `.venv/` son locales y no se versionan.
