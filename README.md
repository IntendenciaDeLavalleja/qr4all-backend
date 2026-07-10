# QR4All Lavalleja — Backend

Backend REST desarrollado con Flask para el generador de QR y enlaces cortos de Lavalleja.

## Stack

| Capa | Tecnología |
|---|---|
| Framework | Flask 3.x |
| ORM | Flask-SQLAlchemy + Alembic |
| Auth | Flask-JWT-Extended (JWT + 2FA por email) |
| DB | MariaDB / SQLite (desarrollo) |
| QR | qrcode + Pillow |
| UA Parsing | user-agents |

## Estructura

```
backend/
  app/
    api/          # Blueprints REST: auth, users, links, qr, analytics, redirect
    models/       # Modelos ORM: User, Link, ClickEvent, QrCode
    services/     # link_service, qr_service, analytics_service, url_validator, email_service
    utils/        # Helpers de logging
    config.py     # Configuración desde variables de entorno
    extensions.py # db, migrate, mail, jwt, limiter
```

## Setup

### 1. Entorno virtual

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Variables de entorno

Copiar `backend/.env.example` a `.env` para desarrollo local.
Para Coolify, usar `backend/.env.production.example` como referencia de
variables de entorno.

### 4. Inicializar base de datos

```bash
flask db init       # Solo primera vez
flask db migrate -m "Initial migration"
flask db upgrade
```

### 5. Crear administrador

```bash
flask create-admin "Nombre Apellido" admin@ejemplo.com ContraseniaSegura true
```

### 6. Datos de demo (opcional)

```bash
flask seed-qr-demo
```

### 7. Levantar el servidor

Desarrollo:
```bash
flask run
```

Producción:
```bash
gunicorn wsgi:app -w 4 -b 0.0.0.0:5000
```

## Roles

| Rol | Descripción |
|-----|-------------|
| `super_admin` | Acceso completo + auditoría |
| `admin` | Gestión de enlaces y usuarios |
| `user` | Creación de enlaces |
