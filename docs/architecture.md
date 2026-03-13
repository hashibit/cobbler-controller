# Architecture

## System Architecture

```
                    ┌─────────────────────────────┐
                    │   USERS / CLIENTS           │
                    │   (REST API + JWT Auth)     │
                    └─────────────┬───────────────┘
                                  │ HTTP
                                  ▼
                    ┌─────────────────────────────┐
                    │   COBBLER CONTROLLER        │
                    │   Flask + Gevent :5000      │
                    └─────┬──────┬─────────┬──────┘
                          │      │         │
                 XML-RPC  │      │ Git     │ SSH
                          │      │         │
        ┌──────────────────▼┐  ┌─▼─────────▼──────────┐
        │  COBBLER SERVERS  │  │      GITLAB          │
        │                   │  │   (infra/env.git)    │
        │  ┌─────────────┐  │  └──────────────────────┘
        │  │ cobbler_1   │  │
        │  │ 192.168.1.10│  │
        │  └─────────────┘  │
        │  ┌─────────────┐  │
        │  │ cobbler_2   │  │
        │  │ 192.168.1.11│  │
        │  └─────────────┘  │
        └───────────────────┘

                          │ SSH
                          ▼
        ┌─────────────────────────────────────────────┐
        │         CLUSTER / INFRASTRUCTURE            │
        │  ┌─────────┐ ┌─────────┐ ┌─────────┐        │
        │  │ node_1  │ │ node_2  │ │ node_3  │ ...    │
        │  └─────────┘ └─────────┘ └─────────┘        │
        └─────────────────────────────────────────────┘
                          │
                          │ IPMI (Power Control)
                          ▼
                       [ BMC/BMC ]
```

## Components

| Component | Description | Protocol |
|-----------|-------------|----------|
| **Users / Clients** | External applications or users accessing the API | HTTP + JWT |
| **Cobbler Controller** | Central Flask API server, coordinates all operations | - |
| **Cobbler Servers** | PXE/DHCP servers for OS provisioning | XML-RPC |
| **GitLab** | Repository for environment configurations | Git |
| **Cluster Nodes** | Target infrastructure servers | SSH |
| **IPMI/BMC** | Baseboard Management Controllers for power management | IPMI |

## Data Flow

### System Provisioning Flow

```
1. User creates system via REST API
   ↓
2. Controller validates request
   ↓
3. Controller calls Cobbler XML-RPC API
   ↓
4. Cobbler creates system profile with PXE config
   ↓
5. Server PXE boots → gets OS image → installs
```

### Environment Deployment Flow

```
1. User triggers environment deploy
   ↓
2. Controller syncs environment configs from GitLab
   ↓
3. Controller deploys rainy-deploy.sh to cluster nodes
   ↓
4. Nodes execute ansible playbooks via tmux
   ↓
5. Monitor deploy logs via API
```
