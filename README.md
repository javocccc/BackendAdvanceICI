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


