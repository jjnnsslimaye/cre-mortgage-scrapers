#!/usr/bin/env python3
"""
Simple network connectivity test for Railway
"""
import socket
import sys

print("Testing network connectivity from Railway...", flush=True)

# Test DNS resolution
try:
    print("\n1. Testing DNS resolution for BCFTP.Broward.org...", flush=True)
    ip = socket.gethostbyname("BCFTP.Broward.org")
    print(f"   ✓ DNS resolved to: {ip}", flush=True)
except socket.gaierror as e:
    print(f"   ✗ DNS resolution failed: {e}", flush=True)
    sys.exit(1)

# Test raw socket connection
try:
    print("\n2. Testing raw TCP connection to BCFTP.Broward.org:22...", flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(("BCFTP.Broward.org", 22))
    print(f"   ✓ TCP connection successful", flush=True)
    sock.close()
except socket.timeout:
    print(f"   ✗ Connection timed out after 10 seconds", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Connection failed: {e}", flush=True)
    sys.exit(1)

# Test SSH banner
try:
    print("\n3. Testing SSH banner exchange...", flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(("BCFTP.Broward.org", 22))
    banner = sock.recv(256).decode('utf-8', errors='ignore')
    print(f"   ✓ Received SSH banner: {banner.strip()}", flush=True)
    sock.close()
except Exception as e:
    print(f"   ✗ Banner exchange failed: {e}", flush=True)
    sys.exit(1)

print("\n✓ All connectivity tests passed!", flush=True)
print("The network path to Broward County FTP is working.", flush=True)
