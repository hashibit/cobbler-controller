# Cobbler Overview

## What is Cobbler?

**Cobbler** is a Linux server installation and configuration management tool for automating operating system deployment. It's widely used in data centers and infrastructure environments to provision servers at scale.

## Core Features

| Feature | Description |
|---------|-------------|
| **PXE Boot** | Network boot servers and automatically install operating systems |
| **DHCP/DNS Management** | Automatically assign IP addresses and manage DNS records |
| **Kickstart Configuration** | Automated installation scripts (similar to Debian Preseed) |
| **Power Management** | Integrated IPMI control for server power (on/off/reset) |
| **System Templates** | Predefined system configuration profiles and templates |
| **Repository Management** | Manage software repositories for installations |

## How It Works

```
1. New Server PXE Boots → 2. Cobbler Provides DHCP/PXE → 3. Gets Kickstart → 4. Auto-Installs OS
```

### Detailed Flow

```
┌───────────┐     PXE Request     ┌──────────┐     DHCP Offer   ┌────────────┐
│  Server   │ ──────────────────► │  DHCP    │ ───────────────► │  Server    │
│  (New)    │                     │ Server   │                  │  (New)     │
│           │                     │          │                  │            │
│ Bare metal│                     │          │                  │ Bare metal │
│ (no OS)   │                     │          │                  │ (no OS)    │
└───────────┘                     └──────────┘                  └────────────┘
     │                               │                               │
     │ DHCP Request includes:        │                               │
     │ - "Next Server" = TFTP IP     │                               │
     ▼                               │                               │
┌──────────┐    TFTP Request    ┌──────────┐     PXE Image    ┌──────────┐
│  Server  │ ─────────────────► │  Cobbler │ ───────────────► │  Server  │
│  (New)   │                    │ TFTP     │                  │  (New)   │
│          │                    │          │                  │          │
└──────────┘                    └──────────┘                  └──────────┘
                                                                  │
                                                                  │ Boots PXE
                                                                  ▼
                                                            ┌───────────┐
                                                            │  Server   │
                                                            │ Installing│
                                                            │    OS     │
                                                            └───────────┘
```

**术语说明**:
- **Server (New)**: 新服务器（裸机），尚未安装操作系统
- **Next Server**: DHCP 选项 66，指定 TFTP 服务器 IP 地址（Cobbler 提供）
- **TFTP**: Trivial File Transfer Protocol，用于传输引导文件

## Key Concepts

### Profiles
A profile defines a specific OS configuration:
- Distribution (CentOS, Ubuntu, etc.)
- Kickstart file
- Repositories
- Kernel parameters

### Systems
A system is a specific server assigned to a profile:
- MAC address
- IP address
- Assigned profile
- IPMI credentials

### Distros
A distribution is the base OS image:
- Kernel and initrd files
- OS version and architecture

### Repositories
Software repositories for package management during installation.

## Cobbler Controller Integration

### In This Project

- **cobbler_1 / cobbler_2**: Cobbler server instances managing different network segments
- **XML-RPC API**: Cobbler Controller uses this interface for remote management
- **Network Mapping**: Different subnets point to different Cobbler servers

```
network_cobblers = {
    "192.168.1.0": cobbler_1,  # Controls servers in 192.168.1.x subnet
    "192.168.2.0": cobbler_2,  # Controls servers in 192.168.2.x subnet
}
```

### API Operations

| Operation | Description |
|-----------|-------------|
| `create_system` | Add a new server to Cobbler |
| `update_system` | Modify existing server configuration |
| `remove_system` | Delete server from Cobbler |
| `get_system` | Retrieve server information |
| `get_systems` | List all servers |
| `sync` | Sync Cobbler configuration |
| `rebuild_system` | Trigger PXE rebuild |
