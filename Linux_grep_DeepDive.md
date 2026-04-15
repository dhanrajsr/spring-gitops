# Linux `grep` — Deep Dive with Complex Queries & Real Scenarios

---

## Anatomy of a grep Command

```
grep [OPTIONS] PATTERN [FILE...]
  │       │       │        │
  │       │       │        └── file(s) or stdin
  │       │       └── regex pattern (BRE by default)
  │       └── flags that change behavior
  └── command
```

**Three regex modes:**
| Flag | Mode | Example |
|------|------|---------|
| *(default)* | BRE — Basic Regex | `grep 'error\|warn'` (need `\|`) |
| `-E` | ERE — Extended Regex | `grep -E 'error\|warn'` (no backslash) |
| `-P` | PCRE — Perl-Compatible | `grep -P '\d{3}-\d{4}'` (full power) |

---

## 1. Basic Flags — Foundation

```bash
grep -i "error" app.log         # Case-insensitive
grep -v "debug" app.log         # Invert match (exclude debug lines)
grep -n "error" app.log         # Show line numbers
grep -c "error" app.log         # Count matching lines only
grep -l "error" /var/log/*.log  # Show only filenames that match
grep -L "error" /var/log/*.log  # Show filenames that DON'T match
grep -o "error" app.log         # Print only the matched part
grep -q "error" app.log         # Quiet — exit code 0/1, no output
grep -w "fail" app.log          # Whole word match only
grep -x "FAILED" app.log        # Whole line must match exactly
```

### Sample Output — `-n`, `-c`, `-o` combined
```bash
grep -in "error" app.log
```
```
42:  [ERROR] Failed to connect to database
87:  [error] Null pointer exception in handler
143: [ERROR] Disk quota exceeded for user root
```

```bash
grep -c "ERROR" app.log
```
```
3
```

```bash
grep -o "ERROR\|WARN\|INFO" app.log | sort | uniq -c | sort -rn
```
```
     89 INFO
     23 WARN
      8 ERROR
```
**Use case:** Quick log level frequency report.

---

## 2. Context Lines — Before, After, Around

```bash
grep -A 3 "ERROR" app.log      # 3 lines After match
grep -B 3 "ERROR" app.log      # 3 lines Before match
grep -C 3 "ERROR" app.log      # 3 lines before and after (Context)
```

### Sample Output — `-C 3`
```bash
grep -C 3 "NullPointerException" app.log
```
```
2024-01-15 10:30:01 [INFO]  Processing request for user_id=4521
2024-01-15 10:30:01 [INFO]  Fetching record from DB
2024-01-15 10:30:01 [WARN]  DB response slow: 2300ms
--
2024-01-15 10:30:02 [ERROR] NullPointerException in UserService.java:87
2024-01-15 10:30:02 [ERROR] Stack trace:
2024-01-15 10:30:02 [ERROR]   at com.app.UserService.getUser(UserService.java:87)
2024-01-15 10:30:02 [INFO]  Request failed, returning 500
```
**Use case:** See what led to an error and what happened after — critical for Root Cause Analysis.

---

## 3. Recursive Search — Searching Across Files

```bash
grep -r "password" /etc/          # Recursive through all files
grep -r "TODO" /app/src/          # Find all TODOs in source code
grep -rl "password" /etc/         # Only show filenames
grep -rn "API_KEY" /app/          # With line numbers
grep -ri "secret" /app/           # Case-insensitive recursive
```

### Combined with file type filter
```bash
grep -r --include="*.py" "import os" /app/
grep -r --include="*.conf" "Listen" /etc/
grep -r --exclude="*.log" "error" /var/
grep -r --exclude-dir=".git" "TODO" /project/
```

### Sample Output
```bash
grep -rn --include="*.py" "os.system" /app/
```
```
/app/utils/deploy.py:34:    os.system("rm -rf " + user_input)    ← command injection!
/app/scripts/backup.py:12:  os.system("tar -czf backup.tar.gz " + path)
/app/tests/test_runner.py:8: os.system("pytest")
```
**Use case:** Security audit — find unsafe `os.system()` calls that could lead to command injection.

---

## 4. Multiple Patterns

```bash
# Match either pattern (OR):
grep -E "error|warn|critical" app.log
grep -e "error" -e "warn" -e "critical" app.log   # Multiple -e flags

# Match from file of patterns:
grep -f patterns.txt app.log

# AND logic — chain grep (both patterns must appear in line):
grep "error" app.log | grep "database"            # Line has both "error" AND "database"
```

### Sample — Multi-pattern with line numbers
```bash
grep -En "error|warn|fail|critical" /var/log/syslog | tail -20
```
```
2045:[Mon Jan 15 10:22:01] kernel: WARNING: possible circular locking dependency
2089:[Mon Jan 15 10:23:14] systemd[1]: FAILED to start MySQL Community Server
2102:[Mon Jan 15 10:23:45] mysqld: ERROR 2002 Can't connect to socket
2134:[Mon Jan 15 10:24:01] systemd[1]: mysql.service: Main process exited with error
```

---

## 5. Anchors — Start and End of Line

```bash
grep "^ERROR" app.log           # Line STARTS with ERROR
grep "failed$" app.log          # Line ENDS with "failed"
grep "^$" app.log               # Empty lines only
grep -v "^$\|^#" config.conf    # Remove empty lines AND comment lines
grep "^[0-9]" data.txt          # Lines starting with a digit
```

### Sample — Clean config file output
```bash
grep -v "^$\|^#\|^;" /etc/mysql/mysql.conf.d/mysqld.cnf
```
```
[mysqld]
bind-address = 127.0.0.1
max_connections = 200
innodb_buffer_pool_size = 1G
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```
**Without grep** it would show 80+ lines with comments. **With grep** — only active config lines.

---

## 6. Character Classes & Ranges

```bash
grep "[0-9]" file.txt           # Any digit
grep "[a-zA-Z]" file.txt        # Any letter
grep "[^0-9]" file.txt          # NOT a digit
grep "[aeiou]" file.txt         # Any vowel
grep "^[A-Z]" file.txt          # Lines starting with uppercase
grep "[[:digit:]]" file.txt     # POSIX digit class
grep "[[:alpha:]]" file.txt     # POSIX alpha class
grep "[[:space:]]" file.txt     # Spaces, tabs
grep "[[:upper:]]" file.txt     # Uppercase letters
```

### Sample — Find lines with IP addresses
```bash
grep -E "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" access.log
```
```
192.168.1.100 - - [15/Jan/2024:10:30:01] "GET /api/users HTTP/1.1" 200 1234
10.0.0.55 - - [15/Jan/2024:10:30:02] "POST /login HTTP/1.1" 401 89
172.16.0.1 - - [15/Jan/2024:10:30:03] "GET /admin HTTP/1.1" 403 0
```

---

## 7. Quantifiers — Repetition

```bash
grep -E "colou?r" file          # u is optional: color OR colour
grep -E "go+" file              # one or more o: go, goo, gooo
grep -E "go*" file              # zero or more o: g, go, goo
grep -E "go{2}" file            # exactly 2 o: goo
grep -E "go{2,4}" file          # 2 to 4 o: goo, gooo, goooo
grep -E "go{2,}" file           # 2 or more o
```

### Sample — Find HTTP error codes (4xx, 5xx)
```bash
grep -E '" [45][0-9]{2} ' /var/log/nginx/access.log
```
```
10.0.0.1 - - [15/Jan] "GET /api/v1/users HTTP/1.1" 404 162
10.0.0.2 - - [15/Jan] "POST /login HTTP/1.1" 401 89
10.0.0.3 - - [15/Jan] "GET /home HTTP/1.1" 500 0
10.0.0.4 - - [15/Jan] "PUT /data HTTP/1.1" 503 0
```

```bash
# Count each HTTP error code:
grep -oE '" [45][0-9]{2} ' /var/log/nginx/access.log | sort | uniq -c | sort -rn
```
```
     45  404 
     12  500 
      8  401 
      3  503 
      1  403 
```

---

## 8. PCRE (`-P`) — Advanced Patterns

```bash
# Lookahead — match X only if followed by Y:
grep -P "error(?= in database)" app.log

# Negative lookahead — match X only if NOT followed by Y:
grep -P "failed(?! to login)" app.log

# Lookbehind — match X only if preceded by Y:
grep -P "(?<=user=)\w+" app.log

# Non-greedy match:
grep -P "<.+?>" file.html       # Match shortest HTML tag

# Word boundary:
grep -P "\broot\b" /etc/passwd  # "root" not "chroot" or "rooting"
```

### Sample — Extract specific field with lookbehind
```bash
# Log format: "user=john action=login status=failed"
grep -oP "(?<=user=)\w+" auth.log | sort | uniq -c | sort -rn
```
```
     23 john
     15 admin
      8 root
      4 testuser
```
**Use case:** Find which users are generating the most auth failures.

---

## 9. Real-World Scenarios

### Scenario A: Find All Failed SSH Logins and Their IPs
```bash
grep "Failed password" /var/log/auth.log | grep -oP "from \K[\d.]+" | sort | uniq -c | sort -rn | head -10
```
```
     892 185.220.101.47    ← brute-force attacker!
     234 103.21.58.33
      87 45.142.212.100
      12 192.168.1.50
       3 10.0.0.25
```
**`\K`** = PCRE "reset match" — throws away the "from " part, only captures the IP.

**Fix action:**
```bash
iptables -I INPUT -s 185.220.101.47 -j DROP
fail2ban-client set sshd banip 185.220.101.47
```

---

### Scenario B: Find Slow Queries in MySQL Slow Log
```bash
grep -A 4 "Query_time: [5-9]\|Query_time: [0-9][0-9]" /var/log/mysql/slow.log
```
```
# Time: 2024-01-15T10:30:01
# User@Host: app_user[app_user] @ localhost []
# Query_time: 23.451234  Lock_time: 0.000123 Rows_sent: 1 Rows_examined: 4500000
SET timestamp=1705312201;
SELECT * FROM orders WHERE created_at > '2020-01-01';   ← full table scan!
```

```bash
# Extract just the query times:
grep -oP "Query_time: \K[0-9.]+" /var/log/mysql/slow.log | sort -n | tail -5
```
```
18.234
23.451
31.002
45.123
120.334    ← 2 minute query!
```

---

### Scenario C: Parse Nginx Access Log — Traffic Analysis
```bash
# Top 10 most requested URLs:
grep -oP '"GET \K[^ ]+' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -10
```
```
   4521 /api/v1/health
   1234 /api/v1/users
    892 /api/v1/products
    234 /static/main.js
     89 /favicon.ico
```

```bash
# Find all 500 errors with their URLs:
grep -E '" 500 ' /var/log/nginx/access.log | grep -oP '"(GET|POST|PUT|DELETE) \K[^"]+(?= HTTP)'
```
```
/api/v1/orders/process
/api/v1/payment/confirm
/api/v1/orders/process
```

---

### Scenario D: Find Hardcoded Secrets in Code
```bash
# Find potential hardcoded passwords:
grep -rniP "(password|passwd|pwd|secret|api_key|token)\s*=\s*['\"][^'\"]{6,}" /app/src/
```
```
/app/src/config.py:23:   DB_PASSWORD = "superSecret123!"
/app/src/api.py:45:      api_key = "sk-proj-abc123xyz789"
/app/src/legacy.py:112:  token = "ghp_abcdefghijklmnop"
```

```bash
# Find AWS keys:
grep -rP "AKIA[0-9A-Z]{16}" /app/
```
```
/app/scripts/deploy.sh:8: AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
```

---

### Scenario E: Count Errors per Hour in Log
```bash
grep "\" 5[0-9][0-9] " /var/log/nginx/access.log | grep -oP ":\K\d{2}(?=:\d{2}:\d{2})" | sort | uniq -c
```
```
       2 09
      45 10    ← errors spiked at 10 AM
      12 11
```

---

## 10. grep + Pipes — Power Combinations

```bash
# Frequency analysis:
grep -oE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" access.log | sort | uniq -c | sort -rn

# Act on found files:
grep -rl "old_function" /app/src/ | xargs sed -i 's/old_function/new_function/g'

# Log while displaying:
tail -f app.log | grep "ERROR" | tee /tmp/errors_live.log

# Search compressed logs:
zgrep "ERROR" /var/log/syslog.2.gz
```

---

## 11. Performance Tips for Large Files

```bash
# Fixed-string match (no regex engine) — much faster:
grep -F "exact string" huge_file.log

# Stop after N matches:
grep -m 5 "ERROR" app.log

# Skip binary files:
grep -I "pattern" /app/

# Fastest — bypass locale processing:
LC_ALL=C grep -F "2024-01-15 10:30" huge.log

# Search inside compressed files:
zgrep -i "error" /var/log/*.gz
```

### Benchmark comparison
```
# Slow  (regex on 10GB log):         45.3s
# Fast  (fixed string -F):           12.1s  → 3.7x faster
# Fastest (LC_ALL=C + -F):            4.2s  → 10x faster
```

---

## Quick Reference Card

```
WHAT YOU WANT                          COMMAND
─────────────────────────────────────────────────────────────────
Case-insensitive                       grep -i
Line numbers                           grep -n
Count matches                          grep -c
Invert (exclude)                       grep -v
Whole word only                        grep -w
Files with matches                     grep -l
Files without matches                  grep -L
3 lines after                          grep -A 3
3 lines before                         grep -B 3
3 lines around                         grep -C 3
OR logic                               grep -E "a|b"
AND logic                              grep "a" | grep "b"
Recursive                              grep -r
Include filetype                       grep -r --include="*.py"
Exclude dir                            grep -r --exclude-dir=.git
Extract matched part only              grep -o
PCRE (lookahead, lookbehind)           grep -P
Fixed string (faster)                  grep -F
Compressed files                       zgrep
Quiet (exit code only)                 grep -q
Stop after N matches                   grep -m N
─────────────────────────────────────────────────────────────────
PATTERN SYNTAX (ERE with -E)
─────────────────────────────────────────────────────────────────
.          Any single character          "a.c" = abc, a1c
^          Start of line                 "^Error"
$          End of line                   "failed$"
*          Zero or more                  "go*" = g, go, goo
+          One or more                   "go+" = go, goo
?          Zero or one                   "colou?r"
{n}        Exactly n                     "[0-9]{3}"
{n,m}      Between n and m              "[0-9]{2,4}"
[abc]      Any of a, b, c               "[aeiou]"
[^abc]     Not a, b, or c               "[^0-9]"
(a|b)      a or b                        "(error|warn)"
\b         Word boundary (PCRE -P)       "\broot\b"
\K         Reset match start (PCRE -P)   "from \K[\d.]+"
(?=Y)      Lookahead: X before Y        "error(?= in db)"
(?<=Y)     Lookbehind: X after Y        "(?<=user=)\w+"
```
