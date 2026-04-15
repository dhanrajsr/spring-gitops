# Linux `awk` — Deep Dive with Real-World Scenarios

---

## Anatomy of an awk Command

```
awk [OPTIONS] 'PROGRAM' [FILE...]
               │
               ├── 'BEGIN { }' → runs BEFORE any input is read
               ├── '/PATTERN/ { ACTION }' → runs for each matching line
               └── 'END { }' → runs AFTER all input is processed

awk 'BEGIN { FS=":" } /root/ { print $1, $3 } END { print "done" }' /etc/passwd
     ──────────────   ──────   ────────────   ───────────────────
     setup phase      filter   action         summary phase
```

**Key built-in variables:**
| Variable | Meaning | Default |
|----------|---------|---------|
| `$0` | Entire current line | — |
| `$1, $2...` | Field 1, 2... | — |
| `NF` | Number of fields in current line | — |
| `NR` | Current line (record) number | — |
| `FNR` | Line number within current file | — |
| `FS` | Input field separator | space/tab |
| `OFS` | Output field separator | space |
| `RS` | Input record separator | newline |
| `ORS` | Output record separator | newline |
| `FILENAME` | Current filename | — |

---

## 1. Field Extraction — The Core Use

```bash
# /etc/passwd: root:x:0:0:root:/root:/bin/bash
awk -F: '{print $1}' /etc/passwd           # Print usernames (field 1)
awk -F: '{print $1, $3}' /etc/passwd       # Username and UID
awk -F: '{print $1":"$3}' /etc/passwd      # With custom separator
awk -F: '{print NR, $1}' /etc/passwd       # Line number + username
awk -F: '{print $NF}' /etc/passwd          # Last field (shell)
awk -F: '{print $(NF-1)}' /etc/passwd      # Second to last field
```

### Sample Output
```bash
awk -F: '{print NR"\t"$1"\t"$3"\t"$7}' /etc/passwd | head -5
```
```
1    root        0      /bin/bash
2    daemon      1      /usr/sbin/nologin
3    bin         2      /usr/sbin/nologin
4    sys         3      /usr/sbin/nologin
5    sync        4      /bin/sync
```

---

### Change Field Separator in Output (OFS)
```bash
awk -F: 'BEGIN{OFS=","} {print $1,$3,$6}' /etc/passwd
```
```
root,0,/root
daemon,1,/usr/sbin
bin,2,/bin
```
**Use case:** Convert `/etc/passwd` to CSV format.

---

### Print Specific Fields from Nginx Access Log
```bash
# Log format: IP - - [date] "METHOD URL HTTP/ver" STATUS SIZE
awk '{print $1, $7, $9}' /var/log/nginx/access.log | head -5
```
```
192.168.1.10  /api/users   200
10.0.0.55     /login       401
172.16.0.1    /admin       403
10.0.0.2      /api/data    200
192.168.1.15  /health      200
```

---

## 2. Pattern Matching — Filter Lines

```bash
awk '/error/' app.log                      # Lines containing "error"
awk '/^ERROR/' app.log                     # Lines starting with ERROR
awk '!/debug/' app.log                     # Exclude debug lines (! = negate)
awk '/start/,/end/' file.txt               # Range: from "start" to "end" line
awk 'NR==5' file.txt                       # Only line 5
awk 'NR>=10 && NR<=20' file.txt            # Lines 10 to 20
awk 'NF>0' file.txt                        # Non-empty lines
awk 'length($0)>80' file.txt              # Lines longer than 80 chars
```

### Sample — Range Pattern (extract block between markers)
```bash
awk '/BEGIN_CONFIG/,/END_CONFIG/' app.conf
```
```
BEGIN_CONFIG
  host = 10.0.0.50
  port = 5432
  max_conn = 100
END_CONFIG
```

```bash
# Exclude the marker lines themselves:
awk '/BEGIN_CONFIG/,/END_CONFIG/ {if (!/BEGIN_CONFIG|END_CONFIG/) print}' app.conf
```
```
  host = 10.0.0.50
  port = 5432
  max_conn = 100
```

---

## 3. Conditionals — if/else

```bash
awk '{if ($3 > 100) print $0}' file.txt
awk '{if ($9 >= 500) print "ERROR:", $7; else if ($9 >= 400) print "WARN:", $7}' access.log
awk -F: '{if ($3 == 0) print $1, "is root"; else print $1, "is user"}' /etc/passwd
```

### Sample — Classify HTTP responses
```bash
awk '{
    status = $9
    if (status >= 500)      print "CRITICAL:", $7, status
    else if (status >= 400) print "WARNING:", $7, status
    else if (status >= 300) print "REDIRECT:", $7, status
    else                    print "OK:", $7, status
}' /var/log/nginx/access.log | head -8
```
```
OK:       /api/users     200
WARNING:  /login         401
CRITICAL: /api/process   500
REDIRECT: /old-page      301
OK:       /health        200
WARNING:  /admin         403
CRITICAL: /api/payment   503
OK:       /static/app.js 200
```

---

## 4. Arithmetic — Calculate and Aggregate

```bash
awk '{sum += $1} END {print sum}' numbers.txt           # Sum column
awk '{sum += $1; count++} END {print sum/count}' file   # Average
awk 'BEGIN{max=0} {if($1>max) max=$1} END{print max}' file  # Max value
```

### Sample — Response time statistics from log
```bash
awk '{
    time = $NF
    sum += time
    count++
    if (time > max) max = time
    if (NR==1 || time < min) min = time
    if (time > 1.0) slow++
}
END {
    printf "Requests : %d\n", count
    printf "Avg Time : %.3f s\n", sum/count
    printf "Min Time : %.3f s\n", min
    printf "Max Time : %.3f s\n", max
    printf "Slow (>1s): %d (%.1f%%)\n", slow, (slow/count)*100
}' app.log
```
```
Requests : 8921
Avg Time : 0.187 s
Min Time : 0.002 s
Max Time : 23.451 s
Slow (>1s): 34 (0.4%)
```

---

## 5. Arrays — Counting and Grouping

```bash
# Count occurrences of each value in a field:
awk '{count[$1]++} END {for (k in count) print count[k], k}' file | sort -rn
```

### Sample A — Count HTTP status codes
```bash
awk '{count[$9]++} END {for (s in count) print count[s], s}' /var/log/nginx/access.log | sort -rn
```
```
   8234  200
    892  304
    234  404
     45  500
     12  401
      3  503
```

---

### Sample B — Traffic per IP address
```bash
awk '{bytes[$1] += $10; hits[$1]++}
END {
    for (ip in hits)
        printf "%-18s  %6d hits  %10.2f KB\n", ip, hits[ip], bytes[ip]/1024
}' /var/log/nginx/access.log | sort -k3 -rn | head -5
```
```
192.168.1.100      4521 hits    23401.45 KB
10.0.0.55          1234 hits     8923.12 KB
172.16.0.10         892 hits     4521.78 KB
10.0.0.2            234 hits     1203.45 KB
192.168.1.15         89 hits      234.12 KB
```

---

### Sample C — Errors per service in log
```bash
awk '/\[ERROR\]/ {
    match($0, /\[ERROR\] \[([^]]+)\]/, arr)
    errors[arr[1]]++
}
END {
    print "Service\t\tError Count"
    print "─────────────────────────"
    for (svc in errors)
        printf "%-15s %d\n", svc, errors[svc]
}' app.log | sort -k2 -rn
```
```
Service         Error Count
─────────────────────────
mysql            45
redis             12
api-gateway        8
auth-service       3
```

---

## 6. String Functions

```bash
length($0)              # Length of string
substr($1, 2, 4)        # Substring: start at pos 2, length 4
index($1, "str")        # Find position of "str" in $1
split($1, arr, ":")     # Split field into array by delimiter
sub(/old/, "new", $0)   # Replace FIRST match
gsub(/old/, "new", $0)  # Replace ALL matches
tolower($1)             # Convert to lowercase
toupper($1)             # Convert to uppercase
sprintf("%.2f", $1)     # Format number like printf
match($0, /regex/)      # Match regex, sets RSTART and RLENGTH
```

### Sample — Extract domain from email
```bash
awk -F@ '{print $2}' emails.txt | sort | uniq -c | sort -rn
```
```
      45 gmail.com
      23 company.com
      12 outlook.com
```

### Sample — Reformat dates
```bash
# Input: "2024-01-15 10:30:01" → Output: "15/Jan/2024"
awk '{
    split($1, d, "-")
    months = "JanFebMarAprMayJunJulAugSepOctNovDec"
    month = substr(months, (d[2]-1)*3+1, 3)
    print d[3]"/"month"/"d[1], $2
}' timestamps.txt
```
```
15/Jan/2024 10:30:01
15/Jan/2024 10:30:02
15/Jan/2024 10:31:00
```

---

## 7. Multiple Files — FNR vs NR

```bash
# NR = total lines across ALL files
# FNR = line number within CURRENT file

awk 'FNR==1 {print "=== File:", FILENAME}' file1.txt file2.txt
```

### Sample — Two-file comparison (classic pattern)
```bash
# Find IPs in access.log that are also in blocklist.txt
awk 'NR==FNR {blocked[$1]=1; next} $1 in blocked {print "BLOCKED:", $0}' blocklist.txt access.log
```
```
BLOCKED: 185.220.101.47 - - [15/Jan] "GET /admin HTTP/1.1" 200 1234
BLOCKED: 45.142.212.100 - - [15/Jan] "POST /login HTTP/1.1" 401 89
```
**`NR==FNR`** is true only while reading the FIRST file — loads it into an array. Second file is then checked against it.

---

## 8. BEGIN and END Blocks

```bash
awk 'BEGIN {
    print "Report Generated:", strftime("%Y-%m-%d %H:%M:%S")
    print "─────────────────────────────────"
    FS=":"
    total=0
}
{
    total += $3
}
END {
    print "─────────────────────────────────"
    print "Total users:", NR
    print "Total UID sum:", total
    print "Avg UID:", total/NR
}' /etc/passwd
```
```
Report Generated: 2024-01-15 10:30:01
─────────────────────────────────
─────────────────────────────────
Total users: 42
Total UID sum: 98234
Avg UID: 2339.9
```

---

## 9. printf — Formatted Output

```bash
awk '{printf "%-20s %10s %8.2f%%\n", $1, $2, $3}' data.txt
#    └──────┘ └──────┘ └──────────┘
#    left-pad  right-pad  float 2dp
```

### Sample — Formatted disk usage report
```bash
df -h | awk 'NR==1 {printf "%-20s %6s %6s %6s %8s\n", $1,$2,$3,$4,$5; next}
{
    use = $5+0
    if (use >= 90)      status = "CRITICAL"
    else if (use >= 75) status = "WARNING"
    else                status = "OK"
    printf "%-20s %6s %6s %6s %8s  [%s]\n", $1,$2,$3,$4,$5,status
}'
```
```
Filesystem           Size   Used   Avail     Use%
/dev/sda1            50G    45G    5G         90%  [CRITICAL]
/dev/sdb1           200G    80G   120G        40%  [OK]
/dev/sdc1           100G    78G    22G        78%  [WARNING]
tmpfs                 8G   512M   7.5G         6%  [OK]
```

---

## 10. Real-World Complex Scenarios

### Scenario A — System Resource Report from `ps`
```bash
ps aux | awk 'NR==1 {print; next}
{
    cpu[$11] += $3
    mem[$11] += $4
    count[$11]++
}
END {
    printf "\n%-25s %8s %8s %8s\n", "PROCESS", "CPU%", "MEM%", "COUNT"
    printf "%s\n", "─────────────────────────────────────────────────"
    for (p in cpu)
        printf "%-25s %8.1f %8.1f %8d\n", p, cpu[p], mem[p], count[p]
}' | sort -k3 -rn | head -15
```
```
PROCESS                    CPU%     MEM%    COUNT
─────────────────────────────────────────────────
/usr/bin/python3           45.2     12.3        4
java                       32.1      8.9        2
/usr/sbin/mysqld           12.3      6.7        1
nginx                       2.1      0.8        8
redis-server                0.8      0.4        1
```

---

### Scenario B — CI/CD Pipeline Step Durations
```bash
awk '
/\[START\]/ {
    step = $4
    split($2, t, ":")
    start[step] = t[1]*3600 + t[2]*60 + t[3]
}
/\[END\]/ {
    step = $4
    split($2, t, ":")
    end_time = t[1]*3600 + t[2]*60 + t[3]
    duration = end_time - start[step]
    printf "%-25s %ds", step, duration
    if (duration > 120) printf "  ← SLOW"
    print ""
}' pipeline.log | sort -k2 -rn
```
```
integration-tests        245s  ← SLOW
build-docker-image       180s  ← SLOW
unit-tests                45s
compile                   23s
lint                       8s
checkout                   2s
```

---

### Scenario C — Network Interface Stats from `/proc/net/dev`
```bash
awk 'NR>2 {
    gsub(/:/, "", $1)
    rx_mb = $2/1024/1024
    tx_mb = $10/1024/1024
    printf "%-10s  RX: %8.2f MB  TX: %8.2f MB  RX_errors: %s  RX_drops: %s\n",
           $1, rx_mb, tx_mb, $4, $5
}' /proc/net/dev
```
```
eth0        RX:  93.68 MB  TX:  43.56 MB  RX_errors: 0  RX_drops: 12
lo          RX:  11.77 MB  TX:  11.77 MB  RX_errors: 0  RX_drops: 0
docker0     RX:   0.00 MB  TX:   2.34 MB  RX_errors: 0  RX_drops: 0
```

---

### Scenario D — Errors Per Minute with Spike Detection
```bash
awk '/ERROR/ {
    split($2, t, ":")
    bucket = $1" "t[1]":"t[2]
    errors[bucket]++
}
END {
    print "Timestamp           Errors"
    print "──────────────────────────"
    n = asorti(errors, sorted)
    for (i=1; i<=n; i++)
        printf "%-20s %4d %s\n", sorted[i], errors[sorted[i]], \
               (errors[sorted[i]]>10 ? "⚠ SPIKE" : "")
}' app.log
```
```
Timestamp           Errors
──────────────────────────
2024-01-15 10:28       2
2024-01-15 10:29       1
2024-01-15 10:30      34 ⚠ SPIKE
2024-01-15 10:31      28 ⚠ SPIKE
2024-01-15 10:32       3
```

---

### Scenario E — CSV Sales Report
```bash
# sales.csv: region,product,quantity,price
awk -F, 'NR==1 {next}
{
    region[$1] += $3 * $4
    product[$2] += $3
    total += $3 * $4
}
END {
    print "=== Revenue by Region ==="
    for (r in region)
        printf "  %-10s $%10.2f\n", r, region[r]

    print "\n=== Units Sold by Product ==="
    for (p in product)
        printf "  %-10s %6d units\n", p, product[p]

    printf "\n  Total Revenue: $%.2f\n", total
}' sales.csv
```
```
=== Revenue by Region ===
  North      $  2498.25
  South      $  3997.50

=== Units Sold by Product ===
  Widget         300 units
  Gadget         125 units

  Total Revenue: $6495.75
```

---

### Scenario F — Kubernetes Pod Restart Monitor
```bash
kubectl get pods -A | awk 'NR==1 {print; next}
{
    restarts = $5
    status = $4
    namespace = $1
    pod = $2

    if (restarts > 10)      severity = "CRITICAL"
    else if (restarts > 3)  severity = "WARNING"
    else                    severity = "OK"

    if (severity != "OK" || status != "Running")
        printf "%-12s %-40s %-10s %5s restarts [%s]\n",
               namespace, pod, status, restarts, severity
}' | sort -k5 -rn
```
```
production   payment-service-7d9f-xk2p9    CrashLoop    23 restarts [CRITICAL]
staging      auth-service-5c8b-m3n1q       Running      15 restarts [CRITICAL]
default      worker-deployment-abc12        Running       5 restarts [WARNING]
production   api-gateway-6f7d-p9q8r        Running       4 restarts [WARNING]
```

---

### Scenario G — Config Drift Detection Across Servers
```bash
awk -F= '
{
    values[$1][FILENAME] = $2
}
END {
    for (key in values) {
        first = ""
        drift = 0
        for (file in values[key]) {
            if (first == "") first = values[key][file]
            else if (values[key][file] != first) drift = 1
        }
        if (drift) {
            print "DRIFT DETECTED: " key
            for (file in values[key])
                printf "  %-30s = %s\n", file, values[key][file]
        }
    }
}' server1.conf server2.conf server3.conf
```
```
DRIFT DETECTED: max_connections
  server1.conf                   = 100
  server2.conf                   = 200
  server3.conf                   = 100
```

---

## 11. awk + Pipes — Power Combinations

```bash
# Top 5 memory consuming processes:
ps aux | awk 'NR>1 {print $4, $11}' | sort -rn | head -5

# Count lines of code per file type:
find /app -type f | awk -F. '{ext[$NF]++} END {for (e in ext) print ext[e], e}' | sort -rn

# Running total:
awk '{total += $1; print $0, "| running total:", total}' numbers.txt

# Print every Nth line:
awk 'NR % 5 == 0' file.txt

# Pass shell variable into awk:
THRESHOLD=500
awk -v thresh="$THRESHOLD" '$3 > thresh {print}' data.txt

# Print lines between line numbers:
awk -v start=10 -v end=20 'NR>=start && NR<=end' file.txt
```

---

## 12. Reusable awk Script File

```bash
# Save as report.awk and run with: awk -f report.awk /var/log/nginx/access.log
cat > report.awk << 'EOF'
BEGIN {
    FS = " "
    print "═══════════════════════════════════════"
    print "         NGINX ACCESS REPORT           "
    print "═══════════════════════════════════════"
}
{
    status = $9
    bytes  = $10
    total_req++
    total_bytes += bytes
    status_count[status]++
    if (status >= 500) errors++
    if (status >= 400 && status < 500) warnings++
}
END {
    printf "\nTotal Requests : %d\n", total_req
    printf "Total Data     : %.2f MB\n", total_bytes/1024/1024
    printf "Errors (5xx)   : %d (%.2f%%)\n", errors, (errors/total_req)*100
    printf "Warnings (4xx) : %d (%.2f%%)\n", warnings, (warnings/total_req)*100
    print "\n─── Status Code Breakdown ───"
    for (s in status_count)
        printf "  HTTP %-3s : %d\n", s, status_count[s]
}
EOF
```
```
═══════════════════════════════════════
         NGINX ACCESS REPORT
═══════════════════════════════════════

Total Requests : 8921
Total Data     : 234.56 MB
Errors (5xx)   : 45 (0.50%)
Warnings (4xx) : 234 (2.62%)

─── Status Code Breakdown ───
  HTTP 200 : 8234
  HTTP 304 :  408
  HTTP 404 :  189
  HTTP 401 :   45
  HTTP 500 :   45
```

---

## Quick Reference Card

```
WHAT YOU WANT                            AWK PATTERN
────────────────────────────────────────────────────────────────
Print field N                            {print $N}
Print last field                         {print $NF}
Print second-to-last                     {print $(NF-1)}
Sum a column                             {s+=$1} END{print s}
Average a column                         {s+=$1;c++} END{print s/c}
Count occurrences                        {a[$1]++} END{for(k in a) print a[k],k}
Skip header line                         NR>1 {print}
Print specific line                      NR==5
Print line range                         NR>=10 && NR<=20
Filter by field value                    $3 > 100
Filter by regex on field                 $2 ~ /pattern/
Exclude regex on field                   $2 !~ /pattern/
Custom input separator                   -F: or -F","
Custom output separator                  BEGIN{OFS=","}
Two-file comparison                      NR==FNR{a[$1]=1;next} $1 in a
Pass shell variable                      -v myvar="$SHELLVAR"
Formatted output                         printf "%-10s %8.2f\n", $1, $2
Replace all in line                      gsub(/old/, "new")
Replace first in line                    sub(/old/, "new")
Extract substring                        substr($1, start, len)
Split field into array                   split($1, arr, ":")
Line length filter                       length($0) > 80
Non-empty lines                          NF > 0
Run code before input                    BEGIN { }
Run code after input                     END { }
────────────────────────────────────────────────────────────────
OPERATORS
────────────────────────────────────────────────────────────────
&&  AND          ||  OR           !   NOT
==  equal        !=  not equal    >   greater
~   regex match  !~  no match     += -= *= /=  compound assign
────────────────────────────────────────────────────────────────
STRING FUNCTIONS
────────────────────────────────────────────────────────────────
length(s)          String length
substr(s,i,n)      Substring from i, length n
index(s,"str")     Position of "str" in s
split(s,a,":")     Split s into array a on ":"
sub(/re/,"new",s)  Replace first match
gsub(/re/,"new",s) Replace all matches
match(s,/re/)      Find regex, sets RSTART/RLENGTH
toupper(s)         Uppercase
tolower(s)         Lowercase
sprintf(fmt,...)   Format without printing
────────────────────────────────────────────────────────────────
MATH FUNCTIONS
────────────────────────────────────────────────────────────────
int(x)   sqrt(x)   sin(x)   cos(x)   log(x)   exp(x)
rand()   → 0 to 1 random    srand()  → seed random
```
