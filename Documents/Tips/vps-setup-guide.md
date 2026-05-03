---
layout: default
title: "VPS Setup Guide"
date: 2025-04-06T18:07:58-04:00
---

# Introduction

This guide covers setting up a WireGuard VPN on a Debian-based VPS. We will use a Minecraft server as an example of something that may need to have its traffic port forwarded to the VPS in order to bypass ISP CGNAT.

This assumes you have a remote VPS (I got mine through a DigitalOcean Droplet) and a local Minecraft Server.

Throughout this guide, the following two machines will be referenced:
- VPS (WireGuard VPN Server)
- Peer (Minecraft Server)

# Walkthrough

## 1. Install WireGuard

### VPS and Peer

Update APT and install WireGuard:\
`apt update && apt install -y wireguard`

## 2. Generate WireGuard Keys

### VPS and Peer

Generate WireGuard keys:\
`wg genkey | tee /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key`

Print WireGuard keys:\
`cat /etc/wireguard/private.key`\
`cat /etc/wireguard/public.key`

Secure private keys:\
`chmod 600 /etc/wireguard/private.key`

## 3. Configure WireGuard

### VPS

`nano /etc/wireguard/wg0.conf`
``` text
[Interface]
PrivateKey = <VPS_PRIVATE_KEY>
Address = 10.0.0.1/24
ListenPort = 51820

# Minecraft server peer
[Peer]
PublicKey = <PEER_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32
```

### Peer

`nano /etc/wireguard/wg0.conf`
``` text
[Interface]
PrivateKey = <PEER_PRIVATE_KEY>
Address = 10.0.0.2/24

[Peer]
PublicKey = <VPS_PUBLIC_KEY>
Endpoint = <VPS_PUBLIC_IP>:51820
AllowedIPs = 10.0.0.1/32
PersistentKeepalive = 25
```

## 4. Enable & Start WireGuard

### VPS and Peer

Start WireGuard:\
`systemctl enable wg-quick@wg0`\
`systemctl start wg-quick@wg0`

Check WireGuard connection:\
`wg`

## 5. Setup Port Forwarding and Firewalls

### VPS

Enable IP forwarding:\
`echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf`\
`sysctl -p`

Forward incoming traffic on port 25565 to the peer (10.0.0.2):\
`iptables -t nat -A PREROUTING -p tcp --dport 25565 -j DNAT --to-destination 10.0.0.2:25565`\
`iptables -t nat -A PREROUTING -p udp --dport 25565 -j DNAT --to-destination 10.0.0.2:25565`

Masquerade outgoing packets on port 25565 to appear from the VPS:\
`iptables -t nat -A POSTROUTING -p tcp -d 10.0.0.2 --dport 25565 -j MASQUERADE`\
`iptables -t nat -A POSTROUTING -p udp -d 10.0.0.2 --dport 25565 -j MASQUERADE`

Accept forwarded traffic on port 25565 to the peer:\
`iptables -A FORWARD -p tcp -d 10.0.0.2 --dport 25565 -j ACCEPT`\
`iptables -A FORWARD -p udp -d 10.0.0.2 --dport 25565 -j ACCEPT`

Allow incoming WireGuard VPN traffic:\
`iptables -A INPUT -p udp --dport 51820 -j ACCEPT`

Allow WireGuard VPN subnet traffic (peers communicating with the VPS):\
`iptables -A INPUT -s 10.0.0.0/24 -j ACCEPT`

Allow ICMP from peers:\
`iptables -A INPUT -p icmp -s 10.0.0.0/24 -j ACCEPT`\
`iptables -A OUTPUT -p icmp -d 10.0.0.0/24 -j ACCEPT`

Drop all other incoming traffic by default:\
`iptables -P INPUT DROP`\
`iptables -P FORWARD DROP`\
`iptables -P OUTPUT ACCEPT`

Save and persist iptables rules:\
`apt install -y iptables-persistent`\
`netfilter-persistent save`

### Peer

Instead of iptables, we will use ufw on the Minecraft server to keep it simple.

Allow traffic from the VPS:\
`ufw allow from 10.0.0.1`

Enable routed traffic:\
`ufw default allow routed`

Enable IP forwarding:\
`echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf`\
`sysctl -w net.ipv4.ip_forward=1`

Enable and reload UFW:\
`ufw enable`\
`ufw reload`

# Conclusion

Test your connection from a third machine:\
`nc -zv <VPS_PUBLIC_IP> 25565`

If successful, your Minecraft server is now accessible on <VPS_PUBLIC_IP>:25565

# Troubleshooting

If making edits to `/etc/wireguard/wg0.conf`, make sure to run `wg-quick down wg0` prior to changes and `wg-quick up wg0` after the changes are made.

To debug connection or firewall issues, you can view active iptables rules with:\
`iptables -L -v -n`
