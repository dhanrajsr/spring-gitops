# Network Diagnostic Commands — Deep Dive with Sample Outputs

---

## Complete Diagnostic Workflow

```
Start here
    │
    ▼
ping -c 4 <host>
    ├── 100% loss → traceroute (find where it breaks)
    ├── packet loss + high jitter → mtr (find which hop)
    └── OK (host reachable)
         │
         ▼
    curl -v http://<host>:<port>
         ├── Connection refused → ss -tlnp (nothing listening)
         ├── Connection timeout → iptables -L -n (firewall dropping)
         ├── SSL error → openssl check cert
         └── HTTP 4xx/5xx → application-level issue
              │
              ▼
         Still unclear?
              │
              ▼
         tcpdump -i eth0 host <target> and port <port>
              ├── SYN, no SYN-ACK → firewall on server
              ├── SYN, RST → port closed or app refusing
              └── SYN, SYN-ACK, no data → app accepting but hanging
```

---

## 1. `ping -c 4 <host>` — Test Reachability

### What it does
Sends ICMP echo requests to check if a host is alive and measures round-trip time (RTT).

### Sample Output — Healthy
```
PING google.com (142.250.80.46) 56(84) bytes of data.
64 bytes from 142.250.80.46: icmp_seq=1 ttl=117 time=12.3 ms
64 bytes from 142.250.80.46: icmp_seq=2 ttl=117 time=11.8 ms
64 bytes from 142.250.80.46: icmp_seq=3 ttl=117 time=12.1 ms
64 bytes from 142.250.80.46: icmp_seq=4 ttl=117 time=11.9 ms

--- google.com ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3004ms
rtt min/avg/max/mdev = 11.8/12.0/12.3/0.2 ms
```
**Healthy signs:** 0% packet loss, consistent RTT, low mdev (jitter).

---

### Sample Output — Issue: Host Unreachable
```
PING 10.0.0.99 (10.0.0.99) 56(84) bytes of data.
From 10.0.0.1 icmp_seq=1 Destination Host Unreachable
From 10.0.0.1 icmp_seq=2 Destination Host Unreachable

--- 10.0.0.99 ping statistics ---
4 packets transmitted, 0 received, +2 errors, 100% packet loss, time 3022ms
```
**Problem identified:** `Destination Host Unreachable` comes from the **gateway/router**, not the target — route exists but host is offline or ARP fails.

**Fix:**
```bash
# Check if host is actually running
ssh user@10.0.0.99

# Check ARP table — is the MAC resolved?
arp -n | grep 10.0.0.99

# If it's a VM/container, check if it's started
virsh list --all
kubectl get pods -A
```

---

### Sample Output — Issue: Packet Loss + High Latency
```
64 bytes from 10.0.0.5: icmp_seq=1 ttl=64 time=2.1 ms
64 bytes from 10.0.0.5: icmp_seq=2 ttl=64 time=890.3 ms   ← spike
64 bytes from 10.0.0.5: icmp_seq=3 ttl=64 time=1200.4 ms  ← very high
request timeout for icmp_seq 4                              ← dropped

4 packets transmitted, 3 received, 25% packet loss
rtt min/avg/max/mdev = 2.1/697.6/1200.4/508.3 ms
```
**Problem identified:** Intermittent packet loss and high jitter — network congestion, bad cable, overloaded NIC, or flaky wireless.

**Fix:**
```bash
# Check interface errors
ip -s link show eth0

# Sample output showing errors:
# RX: bytes  packets  errors  dropped
#     98234    1023      47      12   ← 47 errors, 12 drops = bad cable or NIC

# Check dmesg for hardware errors
dmesg | grep -i "eth0\|link\|error"

# Reduce MTU if fragmentation suspected
ip link set eth0 mtu 1400
```

---

### ping Flags Reference
```bash
ping -c 4 host          # Send exactly 4 packets
ping -i 0.2 host        # Send every 0.2 seconds (faster)
ping -s 1400 host       # Test with larger packet size (MTU testing)
ping -t 64 host         # Set TTL to 64
ping -W 1 host          # Wait max 1 second per reply
ping -q host            # Quiet mode — only show summary
ping -f host            # Flood ping (root only) — stress test
```

---

## 2. `traceroute <host>` — Trace Network Path

### What it does
Shows every router hop between you and the destination using TTL-decrement. Each hop decrements TTL by 1 and returns ICMP "Time Exceeded" when TTL hits 0.

### Sample Output — Healthy
```
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1 (192.168.1.1)        1.234 ms  1.102 ms  1.089 ms   ← your gateway
 2  100.64.0.1 (100.64.0.1)          5.432 ms  5.211 ms  5.319 ms   ← ISP router
 3  72.14.215.165 (72.14.215.165)   11.234 ms 11.102 ms 11.189 ms   ← Google edge
 4  8.8.8.8 (8.8.8.8)               12.345 ms 12.102 ms 12.089 ms   ← destination
```
**Healthy:** Each hop has low RTT, RTT increases gradually, no gaps.

---

### Sample Output — Issue: Routing Loop
```
 1  192.168.1.1    1.1 ms
 2  10.0.0.1       2.3 ms
 3  10.0.0.254     3.1 ms
 4  10.0.0.1       2.9 ms   ← same as hop 2!
 5  10.0.0.254     3.2 ms   ← same as hop 3! — loop detected
 6  10.0.0.1       3.0 ms
...
30  * * *
```
**Problem identified:** Routing loop — two routers pointing at each other. Packets bounce forever and never reach destination.

**Fix:**
```bash
# Check routing tables on the routers:
ip route show
route -n

# Remove the conflicting route and add correct one:
ip route del 0.0.0.0/0 via 10.0.0.254
ip route add default via 10.0.0.1
```

---

### Sample Output — Issue: Packet Loss at Specific Hop
```
 1  192.168.1.1     1.1 ms   1.0 ms   1.1 ms
 2  100.64.0.1      5.2 ms   5.1 ms   5.3 ms
 3  * * *                                       ← hop 3 drops packets
 4  * * *                                       ← hop 4 drops packets
 5  8.8.8.8        12.3 ms  12.1 ms  12.2 ms   ← destination responds!
```
**Problem identified:** Hops 3 and 4 show `* * *` but destination responds — those routers **block ICMP for security**. This is NOT a real problem.

**How to distinguish real loss from ICMP filtering:**
```bash
# Real loss: destination also shows * * *
# ICMP filtered: only intermediate hops show * * * but destination replies

# Use TCP-based traceroute to bypass ICMP filters:
traceroute -T -p 80 8.8.8.8     # TCP SYN to port 80
traceroute -T -p 443 8.8.8.8    # TCP SYN to port 443
```

---

### traceroute Flags Reference
```bash
traceroute host              # Default (UDP probes)
traceroute -T -p 80 host    # TCP SYN to port 80 (bypasses ICMP filters)
traceroute -I host          # ICMP echo (like ping per hop)
traceroute -n host          # No DNS resolution (faster)
traceroute -m 15 host       # Max 15 hops instead of 30
traceroute -w 2 host        # Wait 2 seconds per probe
traceroute -q 1 host        # Only 1 probe per hop (faster)
```

---

## 3. `mtr <host>` — Live Network Path Analysis

### What it does
Combines `ping` + `traceroute` into a live continuously-updating view. Shows **packet loss per hop** in real time — best tool for intermittent issues.

### Sample Output — Healthy
```
                             My traceroute  [v0.94]
hostname (192.168.1.10)                   2024-01-15 10:30:00

Keys: Help   Display mode   Restart statistics   Order of fields   quit
                                   Packets               Pings
 Host                            Loss%   Snt  Last  Avg  Best  Wrst StDev
 1. 192.168.1.1                   0.0%    20   1.2  1.1  0.9   1.5   0.1
 2. 100.64.0.1                    0.0%    20   5.3  5.2  5.0   5.8   0.2
 3. 72.14.215.165                 0.0%    20  11.2 11.1 10.9  11.8   0.2
 4. 8.8.8.8                       0.0%    20  12.3 12.1 11.8  12.9   0.2
```

**Columns explained:**
| Column | Meaning |
|--------|---------|
| `Loss%` | Packet loss at this hop |
| `Snt` | Packets sent so far |
| `Last` | Last RTT (ms) |
| `Avg` | Average RTT |
| `Best` | Lowest RTT ever |
| `Wrst` | Highest RTT ever |
| `StDev` | Jitter — higher = more unstable |

---

### Sample Output — Issue: Congestion at ISP Hop
```
 Host                            Loss%   Snt  Last   Avg  Best  Wrst  StDev
 1. 192.168.1.1                   0.0%   50   1.1   1.0   0.9   1.4   0.1
 2. 100.64.0.1                    0.0%   50   5.2   5.1   5.0   5.9   0.2
 3. isp-core-router.net          40.0%   50  320.1 280.4   5.1  890.2 201.3  ← PROBLEM
 4. 8.8.8.8                      40.0%   50  325.3 285.1   5.2  892.1 203.1
```
**Problem identified:**
- Hop 3 = ISP core router — 40% loss + StDev of 201ms = **severe congestion or hardware failure at ISP**
- Loss propagates to destination (hop 4 also 40%) confirming it's not ICMP filtering

**Fix:**
```bash
# Generate report to send to ISP:
mtr --report --report-cycles 60 8.8.8.8 > mtr_report.txt
cat mtr_report.txt    # Send this to ISP support

# Temporary workaround — route via backup ISP:
ip route add 8.8.8.8 via <backup_gateway>
```

---

### Sample Output — Issue: Loss Only at Final Hop
```
 Host                            Loss%   Snt  Last  Avg  Best  Wrst StDev
 1. 192.168.1.1                   0.0%   30   1.1  1.0   0.9   1.4  0.1
 2. 10.0.1.1                      0.0%   30   5.2  5.1   5.0   5.8  0.2
 3. 10.0.2.1                      0.0%   30  10.1 10.0   9.8  10.5  0.2
 4. 10.0.0.50 (target)           100.0%  30   0.0  0.0   0.0   0.0  0.0  ← all hops OK but target dead
```
**Problem identified:** All intermediate hops fine but target 100% loss — **service or firewall on target is dropping ICMP**. Host may be up but firewalled.

```bash
# Test actual service, not just ICMP:
curl -v --connect-timeout 5 http://10.0.0.50:80
nc -zv 10.0.0.50 80        # Test TCP port
nmap -p 80,443 10.0.0.50   # Port scan
```

---

### mtr Flags Reference
```bash
mtr host                    # Interactive live mode
mtr --report host           # Non-interactive report (good for scripting)
mtr --report-cycles 60 host # Send 60 packets before generating report
mtr -n host                 # No DNS — show IPs only (faster)
mtr -T -P 80 host           # TCP mode on port 80
mtr -u host                 # UDP mode
mtr --interval 0.5 host     # Send probes every 0.5 seconds
```

---

## 4. `iptables -L -n` — Check Local Firewall

### What it does
Lists all firewall rules. `-L` = list all chains, `-n` = numeric output (no DNS lookups).

### Sample Output — Default (no custom rules)
```
Chain INPUT (policy ACCEPT)
target     prot opt source               destination

Chain FORWARD (policy DROP)
target     prot opt source               destination

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
```
**Healthy:** Policy ACCEPT on INPUT/OUTPUT = nothing being blocked.

---

### Sample Output — With Rules
```
Chain INPUT (policy DROP)                           ← default DROP = strict firewall
target     prot opt source               destination
ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0   state RELATED,ESTABLISHED
ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0   tcp dpt:22
ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0   tcp dpt:443
DROP       tcp  --  192.168.10.0/24      0.0.0.0/0   tcp dpt:8080  ← blocks 8080
REJECT     all  --  0.0.0.0/0            0.0.0.0/0   reject-with icmp-host-prohibited

Chain FORWARD (policy DROP)
target     prot opt source               destination

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
```

**Reading the rules — order matters (top to bottom):**

| Line | Meaning |
|------|---------|
| `policy DROP` | Default: block everything not explicitly allowed |
| `RELATED,ESTABLISHED` | Allow return traffic for existing connections |
| `dpt:22` | Allow SSH inbound |
| `dpt:443` | Allow HTTPS inbound |
| `DROP tcp dpt:8080` | Block port 8080 from `192.168.10.0/24` |
| `REJECT all` | Reject everything else with ICMP error back to client |

---

### Difference: DROP vs REJECT
| Action | Client sees | Behavior |
|--------|-------------|----------|
| `DROP` | Connection timeout (hangs until timeout) | Silent discard |
| `REJECT` | Connection refused (immediate error) | Sends ICMP error back |

---

### Diagnosing a Blocked Connection
```bash
# Show rules with line numbers and live packet/byte counters:
iptables -L -n -v --line-numbers

# Sample output:
# Chain INPUT (policy DROP 0 packets, 0 bytes)
# num   pkts bytes  target  prot  source           destination
# 1    1234  89K   ACCEPT  all   0.0.0.0/0        0.0.0.0/0   state RELATED,ESTABLISHED
# 2      89  5340  ACCEPT  tcp   0.0.0.0/0        0.0.0.0/0   tcp dpt:22
# 3       0     0  DROP    tcp   10.0.1.0/24      0.0.0.0/0   tcp dpt:3000  ← 0 pkts = never hit yet

# Watch live counters while testing from client:
watch -n1 "iptables -L INPUT -n -v --line-numbers"

# Fix — insert allow rule BEFORE the DROP:
iptables -I INPUT 3 -p tcp --dport 3000 -j ACCEPT  # Insert at line 3

# Or delete the DROP rule by line number:
iptables -D INPUT 3

# Make persistent across reboots:
iptables-save > /etc/iptables/rules.v4              # Debian/Ubuntu
service iptables save                               # RHEL/CentOS
```

---

### Common iptables Commands
```bash
# List all rules with line numbers:
iptables -L -n -v --line-numbers

# Allow a port:
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT

# Block an IP:
iptables -I INPUT -s 185.220.101.47 -j DROP

# Delete a rule by line number:
iptables -D INPUT 3

# Flush all rules (WARNING — opens firewall completely):
iptables -F

# Save and restore:
iptables-save > /tmp/rules.bak
iptables-restore < /tmp/rules.bak

# Check if specific port is blocked:
iptables -C INPUT -p tcp --dport 8080 -j ACCEPT   # exit 0 = rule exists
```

---

## 5. `curl -v --connect-timeout 5 http://<host>:<port>`

### What it does
Tests HTTP/HTTPS connectivity with verbose output showing every step of TCP + TLS + HTTP handshake.

### Sample Output — Healthy HTTP
```
* Trying 10.0.0.50:80...
* Connected to 10.0.0.50 (10.0.0.50) port 80 (#0)    ← TCP connected
> GET / HTTP/1.1
> Host: 10.0.0.50
> User-Agent: curl/7.88.1
> Accept: */*
>
< HTTP/1.1 200 OK                                      ← server responded
< Content-Type: text/html
< Content-Length: 1234
<
<!DOCTYPE html>...
* Connection #0 to host 10.0.0.50 left intact
```

---

### Sample Output — Issue: Connection Refused
```
* Trying 10.0.0.50:8080...
* connect to 10.0.0.50 port 8080 failed: Connection refused
* Failed to connect to 10.0.0.50 port 8080 after 0 ms: Connection refused
curl: (7) Failed to connect to 10.0.0.50 port 8080: Connection refused
```
**Problem identified:** Port 8080 has nothing listening. Connection refused instantly (not timeout).

**Fix:**
```bash
# On the server — what's listening?
ss -tlnp | grep 8080

# If nothing: start the application
systemctl start myapp

# Is it listening on wrong interface (localhost only)?
ss -tlnp | grep LISTEN
# If shows: 127.0.0.1:8080 = only accessible locally, not remotely
# Fix in app config: change bind address from 127.0.0.1 to 0.0.0.0
```

---

### Sample Output — Issue: Connection Timeout
```
* Trying 10.0.0.50:8080...
* Connection timeout after 5001ms
* Closing connection 0
curl: (28) Connection timeout after 5001 ms
```
**Problem identified:** No response within 5 seconds — firewall is silently DROPping packets.

**Fix:**
```bash
# Confirm firewall is dropping:
iptables -L -n | grep 8080

# Test from server itself (if loopback works = firewall is the issue):
curl http://localhost:8080

# Add allow rule:
iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
```

---

### Sample Output — Issue: SSL Certificate Error
```
* Trying 10.0.0.50:443...
* Connected to 10.0.0.50 (10.0.0.50) port 443 (#0)
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* SSL certificate problem: certificate has expired
* Closing connection 0
curl: (60) SSL certificate problem: certificate has expired
```
**Problem identified:** TLS handshake fails — certificate expired.

**Fix:**
```bash
# Check certificate expiry:
openssl s_client -connect 10.0.0.50:443 2>/dev/null | openssl x509 -noout -dates
# Output:
# notBefore=Jan 1 00:00:00 2024 GMT
# notAfter=Jan 1 00:00:00 2025 GMT   ← expired!

# Renew Let's Encrypt:
certbot renew --force-renewal
systemctl reload nginx

# Test bypass (development only — never in production):
curl -k https://10.0.0.50:443    # -k = skip cert verification
```

---

### Sample Output — Healthy HTTPS with TLS Details
```
* Trying 10.0.0.50:443...
* Connected to 10.0.0.50 (10.0.0.50) port 443 (#0)
* ALPN: offers h2,http/1.1
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (IN), TLS handshake, CERT verify (15):
* TLSv1.3 (IN), TLS handshake, Finished (20):
* TLSv1.3 (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384   ← cipher suite
* Server certificate:
*  subject: CN=example.com
*  start date: Jan  1 00:00:00 2024 GMT
*  expire date: Jan  1 00:00:00 2025 GMT
*  SSL certificate verify ok.                              ← valid cert
> GET / HTTP/2
< HTTP/2 200
```

---

### curl Flags Reference
```bash
curl -v url                        # Verbose — show full request/response
curl -I url                        # HEAD only — just headers, no body
curl -s url                        # Silent — no progress meter
curl -o /dev/null -w "%{http_code}" url  # Just print HTTP status code
curl --connect-timeout 5 url       # Fail after 5s if no connection
curl --max-time 10 url             # Fail if total request > 10s
curl -k url                        # Skip SSL verification
curl -L url                        # Follow redirects
curl -u user:pass url              # Basic authentication
curl -H "Authorization: Bearer TOKEN" url  # Custom header
curl -X POST -d '{"key":"val"}' -H "Content-Type: application/json" url
curl --resolve host:443:10.0.0.50 https://host  # Force IP (bypass DNS)
```

---

## 6. `tcpdump` — Packet-Level Traffic Capture

### What it does
Captures raw network packets — the **ground truth** for "what is actually on the wire." Nothing is hidden from tcpdump — if a packet exists, tcpdump sees it.

### Sample Output — Basic Capture
```bash
sudo tcpdump -i eth0 -n port 80
```
```
tcpdump: verbose output suppressed, use -v or -vv for full protocol decode
listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes

10:30:01.234567 IP 192.168.1.10.54321 > 10.0.0.50.80: Flags [S], seq 100, win 64240, length 0
10:30:01.235123 IP 10.0.0.50.80 > 192.168.1.10.54321: Flags [S.], seq 200, ack 101, win 65535, length 0
10:30:01.235456 IP 192.168.1.10.54321 > 10.0.0.50.80: Flags [.], ack 201, win 502, length 0
10:30:01.235789 IP 192.168.1.10.54321 > 10.0.0.50.80: Flags [P.], seq 101:280, ack 201, length 179: HTTP: GET / HTTP/1.1
10:30:01.240123 IP 10.0.0.50.80 > 192.168.1.10.54321: Flags [P.], seq 201:1430, ack 280, length 1229: HTTP: HTTP/1.1 200 OK
10:30:01.240456 IP 192.168.1.10.54321 > 10.0.0.50.80: Flags [F.], seq 280, ack 1430, length 0
10:30:01.241000 IP 10.0.0.50.80 > 192.168.1.10.54321: Flags [F.], seq 1430, ack 281, length 0
```

**TCP Flags decoded:**
| Flag | Meaning | When |
|------|---------|------|
| `[S]` | SYN | Client initiating connection |
| `[S.]` | SYN-ACK | Server accepting connection |
| `[.]` | ACK | Acknowledgment |
| `[P.]` | PSH-ACK | Data being pushed |
| `[F.]` | FIN-ACK | Graceful connection close |
| `[R]` | RST | Abrupt reset — connection refused or error |
| `[R.]` | RST-ACK | Reset with acknowledgment |

**Normal TCP lifecycle:**
```
Client                    Server
  |---[S]----------------->|   SYN       (connect)
  |<---------[S.]---------  |   SYN-ACK   (accept)
  |---[.]----------------->|   ACK       (established)
  |---[P.] GET /---------->|   Data      (request)
  |<---------[P.] 200 OK--|   Data      (response)
  |---[F.]---------------->|   FIN       (close)
  |<---------[F.]---------|   FIN-ACK   (closed)
```

---

### Sample Output — Issue: SYN sent, No Reply (Firewall DROPping)
```bash
sudo tcpdump -i eth0 -n host 10.0.0.50 and port 8080
```
```
10:30:01.234567 IP 192.168.1.10.54321 > 10.0.0.50.8080: Flags [S], seq 100, win 64240, length 0
10:30:02.234567 IP 192.168.1.10.54321 > 10.0.0.50.8080: Flags [S], seq 100, win 64240, length 0  ← retransmit after 1s
10:30:04.234567 IP 192.168.1.10.54321 > 10.0.0.50.8080: Flags [S], seq 100, win 64240, length 0  ← retransmit after 2s
# No [S.] ever comes back = DROP rule active
```
**Problem identified:** Client keeps retransmitting SYN — firewall on server silently dropping.

**Fix:**
```bash
# On server:
iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
```

---

### Sample Output — Issue: RST (Port Closed or App Refusing)
```
10:30:01.234567 IP 192.168.1.10.54321 > 10.0.0.50.80: Flags [S], seq 100
10:30:01.235000 IP 10.0.0.50.80 > 192.168.1.10.54321: Flags [R.], seq 0, ack 101  ← RST!
```
**Problem identified:** Server sent RST — port is closed or app rejected the connection.

**Difference from DROP:**
- `DROP` → client retransmits SYN multiple times (no response)
- `REJECT/RST` → client gets immediate RST, stops retrying

---

### Sample Output — Issue: Connection Hangs After Handshake
```
10:30:01.234 IP client > server: Flags [S]
10:30:01.235 IP server > client: Flags [S.]    ← handshake OK
10:30:01.236 IP client > server: Flags [.]
10:30:01.237 IP client > server: Flags [P.] length 179: HTTP: GET /api/slow
# ... silence for 25 seconds ...
10:30:26.890 IP server > client: Flags [P.] length 45: HTTP: HTTP/1.1 504
```
**Problem identified:** TCP handshake completes fine but app takes 25 seconds to respond — **application-level timeout**, not a network issue. Check app logs, database queries, or upstream service.

---

### Useful tcpdump Filters and Commands
```bash
# Capture HTTP traffic and show ASCII content:
sudo tcpdump -i eth0 -A -s 0 port 80

# Capture to file for Wireshark:
sudo tcpdump -i eth0 -w /tmp/capture.pcap
wireshark /tmp/capture.pcap

# Filter by host AND port:
sudo tcpdump -i eth0 host 10.0.0.50 and port 443

# Show DNS queries only:
sudo tcpdump -i eth0 -n port 53

# Show only new connections (SYN packets):
sudo tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0'

# Show ICMP (ping) traffic:
sudo tcpdump -i eth0 icmp

# Capture on all interfaces:
sudo tcpdump -i any -n

# Show traffic between two specific hosts:
sudo tcpdump -i eth0 host 10.0.0.1 and host 10.0.0.2

# Exclude SSH traffic (port 22) to reduce noise:
sudo tcpdump -i eth0 not port 22

# Capture with timestamps in readable format:
sudo tcpdump -i eth0 -tttt port 80

# Stop after capturing N packets:
sudo tcpdump -i eth0 -c 100 port 80
```

---

## Quick Reference Summary

| Symptom | First Command | What to Look For |
|---------|--------------|-----------------|
| Can't reach host | `ping -c 4 host` | % packet loss, `Destination Host Unreachable` |
| Slow connection | `mtr host` | High StDev or Loss% at specific hop |
| Where does it fail | `traceroute host` | Where `* * *` starts and persists to destination |
| Port blocked | `iptables -L -n -v` | DROP/REJECT rule matching the port, packet counters |
| Service not connecting | `curl -v http://host:port` | "Connection refused" vs timeout vs SSL error |
| Ground truth capture | `tcpdump -i eth0 host X and port Y` | SYN without SYN-ACK = DROP; RST = port closed |

---

## Diagnostic Cheat Sheet

```
PROBLEM                          COMMAND                            WHAT TO CHECK
──────────────────────────────────────────────────────────────────────────────────────
Host alive?                      ping -c 4 host                    0% loss = alive
Which hop fails?                 traceroute -n host                Where * * * starts
Intermittent drops?              mtr --report host                 Loss% and StDev per hop
Port open?                       curl -v --connect-timeout 5 url   "Connected" vs refused/timeout
Firewall blocking?               iptables -L -n -v --line-numbers  DROP/REJECT rules + counters
Raw packet truth                 tcpdump -i eth0 host X port Y     SYN→SYN-ACK flow
DNS resolving?                   dig hostname / nslookup hostname  Answer section
SSL cert valid?                  openssl s_client -connect h:443   notAfter date
Port listening?                  ss -tlnp | grep PORT              LISTEN state
App vs network issue?            tcpdump + curl simultaneously     App delay after handshake
──────────────────────────────────────────────────────────────────────────────────────

EXIT CODES (curl):
  0   = Success
  6   = Could not resolve host (DNS failure)
  7   = Connection refused
  28  = Connection timeout
  35  = SSL handshake failure
  51  = SSL cert mismatch
  60  = SSL cert verification failed

TCP FLAGS QUICK DECODE:
  [S]   = SYN      → new connection attempt
  [S.]  = SYN-ACK  → server accepted
  [.]   = ACK       → acknowledged
  [P.]  = PSH-ACK  → data transfer
  [F.]  = FIN-ACK  → graceful close
  [R]   = RST       → abrupt reset / refused
```
