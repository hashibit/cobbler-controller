# Cobbler Controller

A Flask-based web service for managing Cobbler systems and deploying infrastructure environments.

## Overview

Cobbler Controller provides a REST API for managing Linux server provisioning through Cobbler and orchestrating infrastructure deployments. It integrates with Cobbler's XML-RPC API for system management and provides IPMI power control capabilities.

## Features

- **System Management**: Create, update, delete, and query systems in Cobbler
- **Power Control**: Power on/off/reset systems via IPMI
- **System Rebuild**: Rebuild systems with PXE boot
- **Environment Deployment**: Deploy infrastructure environments to clusters
- **JWT Authentication**: Secure API access with JWT tokens
- **Async Operations**: gevent-based concurrent processing

## Requirements

- Python 3.6+
- Cobbler servers
- IPMI-enabled servers

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

### Cobbler Servers

Edit `app/cobbler.py` to configure your Cobbler server endpoints:

```python
cobbler_1 = ServerProxy("http://192.168.1.10/cobbler_api")
cobbler_2 = ServerProxy("http://192.168.1.11/cobbler_api")

network_cobblers = {
    "192.168.1.0": cobbler_1,
    "192.168.2.0": cobbler_2,
}
```

### Environment Git Repository

Edit `app/env.py` to configure the environment repository:

```python
default_git_username = "rainy-robot"
default_git_password = "your-password"
envs_git_repo = "http://%s:%s@gitlab.example.com/rainy/infra/env.git"
```

Or set environment variables:

```bash
export GIT_USERNAME=your_username
export GIT_PASSWORD=your_password
```

## Running

```bash
python server.py
```

The server runs on port 5000 by default.

## API Endpoints

### Authentication

All endpoints (except `/envs/<name>/deploy/log`) require JWT authentication.

**Login**:
```
POST /auth
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

Include the token in the `Authorization` header:
```
Authorization: Bearer <access_token>
```

### Systems

**List all systems**:
```
GET /systems
```

**Get system by name**:
```
GET /systems/<name>
```

**Get system by IP**:
```
GET /systems/ip/<ip>
```

**Create system**:
```
POST /systems
Content-Type: application/json

{
  "name": "server01",
  "profile": "CentOS-7-Minimal-1708-x86_64",
  "ks": "/var/lib/cobbler/kickstarts/CentOS-7-Minimal-1708-x86_64.cfg",
  "network_if": {
    "name": "eth100",
    "cidr": "192.168.1.100/24",
    "mac": "00:11:22:33:44:55",
    "dns": "192.168.1.1",
    "gateway": "192.168.1.254"
  },
  "ipmi": {
    "username": "admin",
    "password": "password",
    "address": "192.168.1.50"
  }
}
```

**Update system**:
```
POST /systems/<name>
Content-Type: application/json
```

Same payload as create, all fields optional.

**Delete system**:
```
DELETE /systems/<name>
```

**Rebuild system**:
```
POST /systems/<name>/rebuild
Content-Type: application/json

{
  "boot_mode": "legacy"
}
```

**Power control**:
```
POST /systems/<name>/power_on
POST /systems/<name>/power_off
POST /systems/<name>/power_reset
```

### Admin

**Sync Cobbler**:
```
POST /admin/systems/sync
```

**Find duplicate systems**:
```
POST /admin/systems/find_dup
```

**Clear cache**:
```
POST /admin/systems/clear_cache
```

### Environments

**List environments**:
```
GET /envs
```

**Get environment**:
```
GET /envs/<name>
```

**Deploy environment**:
```
POST /envs/<name>/deploy
Content-Type: application/json

{
  "infra_version": "master",
  "registry_version": "online",
  "yum_version": "online",
  "receivers": "email@example.com",
  "is_rebuild": true,
  "product": "su"
}
```

**Get deploy log**:
```
GET /envs/<name>/deploy/log
```

**Sync environments**:
```
POST /envs/sync
```

### Monitoring

**Monitor threads**:
```
GET /threads_monitor
```

## Project Structure

```
cobbler-controller/
├── server.py              # Main entry point
├── requirements.txt       # Python dependencies
├── app/
│   ├── app.py            # Flask application & routes
│   ├── cobbler.py        # Cobbler API integration
│   ├── deploy.py         # Deployment functionality
│   ├── env.py            # Environment management
│   ├── ipmi.py           # IPMI operations
│   ├── user.py           # User authentication
│   ├── errors.py         # Custom errors
│   ├── thread_group.py   # Thread management
│   ├── utils.py          # Utilities
│   └── worker.py         # Background workers
└── scripts/
    └── rainy-deploy.sh   # Deployment script
```

## License

MIT License