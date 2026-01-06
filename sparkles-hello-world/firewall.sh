#!/bin/bash
echo "Setting up firewall rules..."
# Minimal firewall setup
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
iptables -A INPUT -p tcp --dport 18080 -j ACCEPT
iptables -A INPUT -p tcp --dport 18089 -j ACCEPT
iptables -A INPUT -j DROP
echo "Firewall configured"
