---
layout: default
title: "FRP Setup Guide"
date: 2026-02-16T12:52:00-05:00
---

# Introduction

This guide explains how to securely expose a dedicated server to the public internet using **FRP (Fast Reverse Proxy)** and a separate **VPS (Virtual Private Server)**.

This setup is especially useful if your home internet connection is behind **CGNAT (Carrier-Grade NAT)**. When behind CGNAT, you cannot forward ports on your router because your ISP does not provide you with a true public IPv4 address. As a result, servers hosted at home are unreachable from the internet.

In this guide, we use (with a **Valheim** server as the example):

- **FRPC (client)** running on the same machine as the **Valheim server** (your home server)
- **FRPS (server)** running on a **DigitalOcean Droplet** (your VPS with a public IP)

## Architecture Overview

```
Internet Players
        |
        V
DigitalOcean VPS (Public IP)
    frps (TLS + token auth)
    Opens ports 2456-2458 TCP+UDP
        |
        V
Encrypted FRP Tunnel (TLS)
        |
        V
Home Server (Behind NAT)
    frpc (client)
    Valheim server
```

---

# Walkthrough

> **Important FRP config note:** FRP INI config is deprecated. Use **TOML** (`frps.toml`, `frpc.toml`).

---

## 1 - FRPS Setup (on VPS / DigitalOcean Droplet)

### 1.1 - Install Dependencies

```bash
apt update &&  apt install curl wget tar openssl -y
```

### 1.2 - Create TLS Certificates (Proper CA Method, with SAN)

We will create:
- a **private CA** (`ca.crt` / `ca.key`)
- a **server certificate** for `frps` signed by that CA (`frps.crt` / `frps.key`)
- a copy of `ca.crt` that will be installed on the Valheim server so `frpc` can validate `frps`

#### 1.2.1 - Create Directory for Certs

```bash
mkdir -p /etc/frp/certs
chmod 700 /etc/frp
chmod 700 /etc/frp/certs
cd /etc/frp/certs
```

#### 1.2.2 - Create a Certificate Authority (CA)

```bash
# CA private key
openssl genrsa -out ca.key 4096

# CA certificate
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650   -subj "/CN=frp-private-ca"   -out ca.crt
```

Lock down CA key:

```bash
chmod 600 ca.key
chmod 644 ca.crt
```

#### 1.2.3 - Create a SAN config (Domain OR IP)

**Pick ONE:**

**A) If you have a domain** (recommended):
- Replace `frp.example.com` with your real hostname.
- Make sure DNS A record points to your VPS public IP.

**B) If you are using ONLY an IP address**:
- Replace `frp.example.com` with your VPS public IP.

```bash
nano san.cnf
```

```cnf
[req]
distinguished_name = dn
req_extensions = v3_req
prompt = no

[dn]
CN = frp.example.com

[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = frp.example.com
```

#### 1.2.4 - Create FRPS Server Key + CSR

```bash
openssl genrsa -out frps.key 4096
openssl req -new -key frps.key -out frps.csr -config san.cnf
```

#### 1.2.5 - Sign the FRPS Server Certificate with the CA

```bash
openssl x509 -req -in frps.csr -CA ca.crt -CAkey ca.key -CAcreateserial   -out frps.crt -days 825 -sha256 -extensions v3_req -extfile san.cnf
```

Secure permissions:

```bash
chmod 600 frps.key
chmod 644 frps.crt
```

#### 1.2.6 - (Later) Copy the CA cert to the Valheim server

You will do this in section **2.3**.

---

### 1.3 - Install FRP

```bash
VERSION=$(curl -s https://api.github.com/repos/fatedier/frp/releases/latest | grep tag_name | cut -d '"' -f4)

wget https://github.com/fatedier/frp/releases/download/$VERSION/frp_${VERSION}_linux_amd64.tar.gz
tar xzf frp_${VERSION}_linux_amd64.tar.gz
mv frp_${VERSION}_linux_amd64 /opt/frp
```

### 1.4 - Configure FRP Server (frps.toml)

```bash
nano /opt/frp/frps.toml
```

```toml
# frps.toml (VPS / DigitalOcean)
bindPort = 7000

# Authentication
auth.method = "token"
auth.token = "ChangeThisToAVeryLongRandomString!"
auth.additionalScopes = ["HeartBeats", "NewWorkConns"]

# Restrict allowed ports (prevents abuse)
allowPorts = [
  { start = 2456, end = 2458 }
]

# Enforce TLS-only connections
transport.tls.force = true
transport.tls.certFile = "/etc/frp/certs/frps.crt"
transport.tls.keyFile  = "/etc/frp/certs/frps.key"
```

> Why port **7000**? It’s the standard default in the FRP docs, widely used in examples, and avoids conflicts with real HTTPS services on 443.  
> You *can* change it, but then you must also update: `frpc.toml` + UFW rules.

### 1.5 - Create FRPS systemd Service

#### 1.5.1 - Create Service File

```bash
nano /etc/systemd/system/frps.service
```

```ini
[Unit]
Description=FRP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/frp
ExecStart=/opt/frp/frps -c /opt/frp/frps.toml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 1.5.2 - Enable and Start FRPS

```bash
systemctl daemon-reload
systemctl enable --now frps
systemctl status frps
```

### 1.6 - Harden VPS Firewall (UFW)

```bash
apt install ufw -y
ufw --force reset

ufw default deny incoming
ufw default allow outgoing

# SSH
ufw allow 22/tcp
ufw limit 22/tcp

# FRP control port
ufw allow 7000/tcp

# Valheim public ports
ufw allow 2456:2458/tcp
ufw allow 2456:2458/udp

ufw enable
ufw status verbose
```

---

## 2 - FRPC Setup (on Valheim Server / Home Server)

### 2.1 - Install Dependencies

```bash
apt update &&  apt install curl wget tar -y
```

### 2.2 - Install FRP Client

Make sure to download the same version as the VPS so FRPC is compatible with FRPS.

```bash
VERSION=$(curl -s https://api.github.com/repos/fatedier/frp/releases/latest | grep tag_name | cut -d '"' -f4)

wget https://github.com/fatedier/frp/releases/download/$VERSION/frp_${VERSION}_linux_amd64.tar.gz
tar xzf frp_${VERSION}_linux_amd64.tar.gz
mv frp_${VERSION}_linux_amd64/frpc /usr/local/bin/
```

### 2.3 - Install the CA Certificate from the VPS (Required)

On the **VPS**, output the CA cert:

```bash
cat /etc/frp/certs/ca.crt
```

Copy the full contents and paste it on the **Valheim server** into:

```bash
mkdir -p /etc/frp/certs
chmod 700 /etc/frp
chmod 700 /etc/frp/certs
nano /etc/frp/certs/ca.crt
```

Then set permissions:

```bash
chmod 644 /etc/frp/certs/ca.crt
```

### 2.4 - Configure FRP Client (frpc.toml)

```bash
nano ~/frpc.toml
```

```toml
# frpc.toml (Valheim server / home)
serverAddr = "YOUR_VPS_IP_OR_DOMAIN"
serverPort = 7000

# Authentication
auth.method = "token"
auth.token = "ChangeThisToAVeryLongRandomString!"
auth.additionalScopes = ["HeartBeats", "NewWorkConns"]

# TLS
transport.tls.enable = true
transport.tls.trustedCaFile = "/etc/frp/certs/ca.crt"

[[proxies]]
name = "valheim-tcp"
type = "tcp"
localIP = "127.0.0.1"
localPort = 2456
remotePort = 2456

# Optional but recommended: remove the proxy if Valheim isn't reachable
healthCheck.type = "tcp"
healthCheck.timeoutSeconds = 3
healthCheck.maxFailed = 3
healthCheck.intervalSeconds = 10

[[proxies]]
name = "valheim-udp1"
type = "udp"
localIP = "127.0.0.1"
localPort = 2456
remotePort = 2456

[[proxies]]
name = "valheim-udp2"
type = "udp"
localIP = "127.0.0.1"
localPort = 2457
remotePort = 2457

[[proxies]]
name = "valheim-udp3"
type = "udp"
localIP = "127.0.0.1"
localPort = 2458
remotePort = 2458
```

### 2.5 - Create FRPC systemd Service

#### 2.5.1 - Create Service File

```bash
nano /etc/systemd/system/frpc.service
```

```ini
[Unit]
Description=FRP Client
After=network-online.target

[Service]
ExecStart=/usr/local/bin/frpc -c /home/youruser/frpc.toml
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

#### 2.5.2 - Enable and Start FRPC

```bash
systemctl daemon-reload
systemctl enable --now frpc
systemctl status frpc
```

### 2.6 - Harden Valheim Server Firewall (UFW)

You do **NOT** need to open Valheim ports on the home firewall; FRPC makes an outbound connection to the VPS and exposes the ports *there*.

```bash
apt install ufw -y
ufw --force reset

ufw default deny incoming
ufw default allow outgoing

# SSH (only if needed)
ufw allow 22/tcp
ufw limit 22/tcp

# Allow Valheim from local network only (change to your local subnet)
ufw allow from 172.16.0.0/24 to any port 2456:2458 proto tcp
ufw allow from 172.16.0.0/24 to any port 2456:2458 proto udp

ufw enable
ufw status verbose
```

---

# Validation / Troubleshooting

## Check FRPS logs (VPS)

```bash
journalctl -u frps -f
```

## Check FRPC logs (Valheim server)

```bash
journalctl -u frpc -f
```

## Player connection info

Players connect to your **VPS public IP (or domain)** on **port 2456**.

---

# Notes

- If you're using a domain, `serverAddr` should be the domain. If you're using IP, it should be the IP.
- If you regenerate certs, you must copy the updated `ca.crt` to the Valheim server again.
