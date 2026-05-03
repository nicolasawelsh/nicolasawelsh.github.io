---
layout: default
title: "UFW Reference"
date: 2024-06-21T18:20:59-04:00
---

# Introduction

UFW is a frontend tool for the iptables Linux firewall that makes it easy to implement custom local firewall rules. It is important to note that UFW is typically disabled by default.

# Usage

Enable UFW:\
`ufw enable`

Disable ufw:\
`ufw disable`

List UFW rules:\
`ufw status verbose`

List UFW rules (numbered):\
`ufw status numbered`

List available UFW profiles:\
`ufw app list`

# Practical Examples

Allow SSH access from internal network (ex: 172.16.0.0/24):\
`ufw allow from 172.16.0.0/24 to any port 22`

Allow port 25565 access from anywhere:\
`ufw allow 25565`

Find and delete a UFW rule:\
`ufw status numbered`\
`ufw delete 3`

# References

- https://www.digitalocean.com/community/tutorials/ufw-essentials-common-firewall-rules-and-commands
- https://help.ubuntu.com/community/UFW

