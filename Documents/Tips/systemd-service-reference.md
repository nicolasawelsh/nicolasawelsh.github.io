---
layout: default
title: "Systemd Service Reference"
date: 2024-06-22T15:17:57-04:00
---

# Introduction

Services can be created in Linux using systemd services. Custom unit configuration files created by the system administrator can be made under the '/etc/systemd/system' directory and then managed using the systemctl tool. 

# Practical Example

I want to create a systemd service for a Palworld server.

Create systemd service:\
`vim /etc/systemd/system/palworld.serivce`

Contents of 'palworld.serivce':
``` text
[Unit]
Description=Palworld Server
After=network.target

[Service]
User=steam
Group=steam

WorkingDirectory=/home/steam/Steam/steamapps/common/PalServer
ExecStart=/home/steam/Steam/steamapps/common/PalServer/PalServer.sh

TimeoutStartSec=120
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Reload systemd:\
`systemctl daemon-reload`

Enable service:\
`systemctl enable palworld.service`

Start service:\
`systemctl start palworld.service`

# References
- https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html

