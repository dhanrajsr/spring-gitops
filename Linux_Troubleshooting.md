# Linux Troubleshooting Guide — 150 Common Errors (2026 Edition)
> DevOps Shack | Linux System Administration

---

## Table of Contents
1. [Filesystem & Disk Errors](#section-1-filesystem--disk-errors) (#001–#010)
2. [Process & Memory Errors](#section-2-process--memory-errors) (#011–#020)
3. [Networking Errors](#section-3-networking-errors) (#021–#030)
4. [Authentication & User Errors](#section-4-authentication--user-errors) (#031–#040)
5. [Systemd & Service Errors](#section-5-systemd--service-errors) (#041–#050)
6. [Package Management Errors](#section-6-package-management-errors) (#051–#060)
7. [Docker & Container Errors](#section-7-docker--container-errors) (#061–#070)
8. [Kernel & Boot Errors](#section-8-kernel--boot-errors) (#071–#080)
9. [Storage & RAID Errors](#section-9-storage--raid-errors) (#081–#090)
10. [Security Errors](#section-10-security-errors) (#091–#100)
11. [Advanced Networking Errors](#section-11-advanced-networking-errors) (#101–#110)
12. [Programming & Build Errors](#section-12-programming--build-errors) (#111–#120)
13. [Database Errors](#section-13-database-errors) (#121–#130)
14. [CI/CD & Automation Errors](#section-14-cicd--automation-errors) (#131–#140)
15. [Performance & Observability Errors](#section-15-performance--observability-errors) (#141–#150)

---

## Section 1: Filesystem & Disk Errors

### #001 No Space Left on Device

**DESCRIPTION:** Write operations fail because the filesystem has no remaining space.

**ROOT CAUSE:** Disk partition is 100% full.

**CAUSE:** Log files, temp files, core dumps, or large data files consuming all available disk space.

**SOLUTION:**
```bash
df -h                          # Check disk usage
du -sh /* 2>/dev/null | sort -rh | head -20   # Find large directories
find /var/log -name "*.log" -size +100M        # Find large log files
journalctl --vacuum-size=500M  # Trim journal logs
rm -rf /tmp/*                  # Clean temp files
```

---

### #002 Read-Only Filesystem

**DESCRIPTION:** Filesystem remounted read-only; writes fail with "Read-only file system" error.

**ROOT CAUSE:** Kernel detected I/O errors or filesystem corruption and remounted as read-only to prevent further damage.

**CAUSE:** Disk hardware failure, abrupt shutdown, or filesystem journal errors.

**SOLUTION:**
```bash
dmesg | grep -i "read-only\|remount\|error"   # Check kernel messages
fsck -y /dev/sdXN             # Force filesystem check (unmounted)
mount -o remount,rw /          # Remount read-write after fix
```

---

### #003 No Inodes Left (Inode Exhausted)

**DESCRIPTION:** Cannot create new files even though disk space is available.

**ROOT CAUSE:** Inode table is full — too many small files consuming all inodes.

**CAUSE:** Excessive small files (e.g., email spools, PHP sessions, temp files).

**SOLUTION:**
```bash
df -i                          # Check inode usage
find /tmp -type f | wc -l     # Count files in tmp
find /var/spool -type f -delete  # Delete spool files
```

---

### #004 Permission Denied

**DESCRIPTION:** Operation fails with "Permission denied" (EPERM/EACCES).

**ROOT CAUSE:** Process lacks required file permissions or capabilities.

**CAUSE:** Wrong file ownership, incorrect chmod bits, or SELinux/AppArmor policy.

**SOLUTION:**
```bash
ls -la /path/to/file           # Check permissions
chmod 644 /path/to/file        # Fix permissions
chown user:group /path/to/file # Fix ownership
id                             # Verify current user/groups
```

---

### #005 Too Many Open Files

**DESCRIPTION:** Applications fail with "Too many open files" (EMFILE/ENFILE).

**ROOT CAUSE:** File descriptor limit reached for a process or system-wide.

**CAUSE:** File descriptor leak in application or low ulimit setting.

**SOLUTION:**
```bash
ulimit -n                      # Check current limit
lsof -p <pid> | wc -l         # Count open files per process
ulimit -n 65536                # Increase limit for session
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "fs.file-max = 2097152" >> /etc/sysctl.conf && sysctl -p
```

---

### #006 Disk Quota Exceeded

**DESCRIPTION:** User cannot write files; quota limit reached.

**ROOT CAUSE:** User's disk quota (block or inode) is exhausted.

**CAUSE:** User consuming more disk than their quota allows.

**SOLUTION:**
```bash
quota -u username              # Check user quota
repquota -a                    # Report all quotas
edquota -u username            # Edit user quota
quotacheck -cum /home          # Recheck quota
```

---

### #007 No Such File or Directory (ENOENT)

**DESCRIPTION:** File or directory referenced does not exist.

**ROOT CAUSE:** Path is wrong, file was deleted, or symlink is broken.

**CAUSE:** Typo in path, missing file, or dangling symlink.

**SOLUTION:**
```bash
ls -la /path/to/file           # Verify file exists
file /path/to/symlink          # Check if symlink is broken
find / -name "filename" 2>/dev/null   # Locate file
readlink -f /path/to/symlink   # Resolve symlink
```

---

### #008 Input/Output Error

**DESCRIPTION:** Read/write operations fail with "Input/output error" (EIO).

**ROOT CAUSE:** Hardware-level disk failure or bad sector.

**CAUSE:** Failing disk, bad cables, or filesystem corruption.

**SOLUTION:**
```bash
dmesg | grep -i "error\|fail\|bad sector"
smartctl -a /dev/sda           # Check disk health (S.M.A.R.T.)
badblocks -sv /dev/sda         # Scan for bad blocks
fsck -y /dev/sdXN              # Check filesystem
```

---

### #009 Filesystem Corruption (fsck)

**DESCRIPTION:** System boots into emergency mode; fsck reports filesystem errors.

**ROOT CAUSE:** Unexpected shutdown caused inconsistent filesystem state.

**CAUSE:** Power loss during write, kernel panic, or hardware failure.

**SOLUTION:**
```bash
fsck -y /dev/sdXN              # Auto-fix filesystem
e2fsck -p /dev/sdXN            # ext2/3/4 check
xfs_repair /dev/sdXN           # XFS filesystem repair
mount -o ro /dev/sdXN /mnt    # Mount read-only to recover data
```

---

### #010 Mount: Wrong Filesystem Type

**DESCRIPTION:** `mount` fails with "wrong fs type, bad option, bad superblock".

**ROOT CAUSE:** Filesystem type mismatch or corrupted superblock.

**CAUSE:** Specifying wrong `-t` option or filesystem is damaged.

**SOLUTION:**
```bash
file -s /dev/sdXN              # Detect filesystem type
blkid /dev/sdXN                # Show filesystem UUID and type
mount -t ext4 /dev/sdXN /mnt  # Mount with correct type
dumpe2fs /dev/sdXN | grep superblock  # Find backup superblock
```

---

## Section 2: Process & Memory Errors

### #011 Cannot Allocate Memory (ENOMEM)

**DESCRIPTION:** Process fails to start or allocate memory; system returns ENOMEM.

**ROOT CAUSE:** System is out of available RAM and swap.

**CAUSE:** Memory leak, excessive processes, or insufficient RAM/swap.

**SOLUTION:**
```bash
free -h                        # Check memory and swap usage
top -o %MEM                    # Find memory-hungry processes
swapon --show                  # Check swap
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

---

### #012 Segmentation Fault (SIGSEGV)

**DESCRIPTION:** Process crashes with "Segmentation fault" (core dumped).

**ROOT CAUSE:** Process accessed invalid memory address.

**CAUSE:** Bug in application code (null pointer, buffer overflow, use-after-free).

**SOLUTION:**
```bash
ulimit -c unlimited            # Enable core dumps
gdb ./binary core              # Debug with core dump
valgrind --leak-check=full ./binary  # Memory error detection
dmesg | grep segfault          # Check kernel messages
```

---

### #013 OOM Killer Invoked

**DESCRIPTION:** Kernel OOM killer terminates processes to free memory.

**ROOT CAUSE:** System completely out of memory.

**CAUSE:** Memory leak, insufficient RAM, or swap exhausted.

**SOLUTION:**
```bash
dmesg | grep -i "oom\|killed process"
cat /proc/<pid>/oom_score      # Check OOM score
echo -1000 > /proc/<pid>/oom_score_adj  # Protect critical process
free -h && cat /proc/meminfo   # Diagnose memory state
```

---

### #014 Process Not Found

**DESCRIPTION:** `kill` or `ps` shows process does not exist.

**ROOT CAUSE:** Process already terminated or wrong PID specified.

**CAUSE:** Process crashed, completed, or PID was recycled.

**SOLUTION:**
```bash
ps aux | grep process_name     # Find process
pgrep -la process_name         # Search by name
systemctl status service_name  # Check service status
pidof process_name             # Get PID by name
```

---

### #015 Resource Temporarily Unavailable (EAGAIN)

**DESCRIPTION:** System call returns EAGAIN; operation would block or resource unavailable.

**ROOT CAUSE:** Non-blocking I/O or resource limit temporarily reached.

**CAUSE:** Too many processes, threads, or open files; fork limit reached.

**SOLUTION:**
```bash
ulimit -a                      # Check all limits
cat /proc/sys/kernel/threads-max  # Check thread limit
sysctl kernel.pid_max          # Check PID limit
echo 4194304 > /proc/sys/kernel/threads-max
```

---

### #016 Process Killed (Signal 9)

**DESCRIPTION:** Process receives SIGKILL and is forcibly terminated.

**ROOT CAUSE:** OOM killer, admin kill -9, or cgroup memory limit exceeded.

**CAUSE:** Memory exhaustion or intentional forced termination.

**SOLUTION:**
```bash
dmesg | grep killed            # Check OOM killer logs
journalctl -u service_name     # Check service logs
cat /sys/fs/cgroup/memory/*/memory.max_usage_in_bytes  # Check cgroup limits
```

---

### #017 Zombie Process

**DESCRIPTION:** `ps` shows process in 'Z' state (zombie); cannot be killed.

**ROOT CAUSE:** Child process exited but parent has not called `wait()`.

**CAUSE:** Bug in parent process not reaping child processes.

**SOLUTION:**
```bash
ps aux | awk '$8 == "Z"'       # Find zombies
ps -o ppid= -p <zombie_pid>    # Find parent PID
kill -SIGCHLD <parent_pid>     # Signal parent to reap children
kill -9 <parent_pid>           # Kill parent if unresponsive
```

---

### #018 CPU Soft Lockup

**DESCRIPTION:** Kernel logs "BUG: soft lockup - CPU#N stuck for Xs!"

**ROOT CAUSE:** CPU core stuck in kernel code without yielding.

**CAUSE:** Runaway kernel thread, driver bug, or virtualization overhead.

**SOLUTION:**
```bash
dmesg | grep "soft lockup"
echo 0 > /proc/sys/kernel/hung_task_timeout_secs  # Disable hung task detection temporarily
sysctl -w kernel.watchdog_thresh=60  # Increase watchdog threshold
top                            # Check CPU usage by process
```

---

### #019 Load Average Too High

**DESCRIPTION:** System slow; `uptime` or `top` shows load average >> number of CPUs.

**ROOT CAUSE:** Too many runnable or I/O-blocked processes competing for CPU.

**CAUSE:** CPU-bound processes, I/O bottleneck, or disk saturation.

**SOLUTION:**
```bash
uptime                         # Check load average
nproc                          # Number of CPUs
top -bn1 | head -20            # Top processes
iostat -x 1 5                  # Check I/O wait
vmstat 1 5                     # CPU/memory/IO stats
```

---

### #020 ulimit: Max User Processes Reached

**DESCRIPTION:** Cannot fork new processes; "Resource temporarily unavailable" on fork.

**ROOT CAUSE:** `nproc` limit reached for user.

**CAUSE:** Process/thread leak or low `nproc` limit.

**SOLUTION:**
```bash
ulimit -u                      # Check process limit
ps aux | grep username | wc -l # Count user processes
echo "username soft nproc 65536" >> /etc/security/limits.conf
echo "username hard nproc 65536" >> /etc/security/limits.conf
```

---

## Section 3: Networking Errors

### #021 Connection Refused (ECONNREFUSED)

**DESCRIPTION:** TCP connection attempt returns "Connection refused".

**ROOT CAUSE:** No service is listening on the target port, or firewall blocking.

**CAUSE:** Service not running, wrong port, or firewall rule.

**SOLUTION:**
```bash
ss -tlnp | grep <port>         # Check if service is listening
systemctl status <service>     # Check service status
telnet <host> <port>           # Test connectivity
iptables -L -n | grep <port>  # Check firewall rules
```

---

### #022 Connection Timed Out (ETIMEDOUT)

**DESCRIPTION:** Connection attempt hangs and eventually times out.

**ROOT CAUSE:** Packets dropped by firewall or network path issue.

**CAUSE:** Firewall blocking, routing problem, or host unreachable.

**SOLUTION:**
```bash
ping -c 4 <host>               # Test reachability
traceroute <host>              # Trace network path
mtr <host>                     # Live network path analysis
iptables -L -n                 # Check local firewall
curl -v --connect-timeout 5 http://<host>:<port>
```

---

### #023 Network Unreachable

**DESCRIPTION:** `ping` or connections fail with "Network is unreachable".

**ROOT CAUSE:** No route to destination network.

**CAUSE:** Missing or incorrect routing table entry, interface down.

**SOLUTION:**
```bash
ip route show                  # Show routing table
ip addr show                   # Show interfaces
ip link set eth0 up            # Bring interface up
ip route add default via <gateway>  # Add default route
```

---

### #024 DNS Resolution Failure

**DESCRIPTION:** `nslookup`/`dig` fails or hostname cannot be resolved.

**ROOT CAUSE:** DNS server unreachable or misconfigured.

**CAUSE:** Wrong `/etc/resolv.conf`, DNS server down, or NXDOMAIN.

**SOLUTION:**
```bash
cat /etc/resolv.conf           # Check DNS config
dig @8.8.8.8 hostname          # Test with specific DNS
nslookup hostname              # DNS lookup
systemctl restart systemd-resolved  # Restart DNS resolver
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
```

---

### #025 SSH Connection Reset

**DESCRIPTION:** SSH session drops with "Connection reset by peer".

**ROOT CAUSE:** Network interruption, SSH server crash, or firewall timeout.

**CAUSE:** Idle timeout, MTU mismatch, or SSH daemon crash.

**SOLUTION:**
```bash
# Client-side keepalive in ~/.ssh/config:
# ServerAliveInterval 60
# ServerAliveCountMax 3
ssh -v user@host               # Debug SSH connection
journalctl -u sshd             # Check SSH daemon logs
ip link show | grep mtu        # Check MTU
```

---

### #026 Address Already in Use (EADDRINUSE)

**DESCRIPTION:** Service fails to start; port is already bound.

**ROOT CAUSE:** Another process is using the same port.

**CAUSE:** Previous instance still running or port conflict.

**SOLUTION:**
```bash
ss -tlnp | grep <port>         # Find process using port
lsof -i :<port>                # List process on port
kill -9 <pid>                  # Kill conflicting process
systemctl stop <service>       # Stop conflicting service
```

---

### #027 iptables: No Chain/Target/Match by That Name

**DESCRIPTION:** `iptables` command fails with "No chain/target/match by that name".

**ROOT CAUSE:** Missing iptables module or typo in chain/target name.

**CAUSE:** Kernel module not loaded or incorrect rule syntax.

**SOLUTION:**
```bash
lsmod | grep ip_tables         # Check modules
modprobe ip_tables             # Load module
modprobe xt_conntrack          # Load conntrack module
iptables -L                    # List current rules
```

---

### #028 Broken Pipe (EPIPE)

**DESCRIPTION:** Process writing to a pipe fails with "Broken pipe".

**ROOT CAUSE:** Reading end of the pipe closed before writer finished.

**CAUSE:** Reader process exited, network connection dropped, or timeout.

**SOLUTION:**
```bash
# Check if receiving process is still running
ps aux | grep <reader_process>
# Use signal trap in scripts:
trap '' PIPE
# For SSH/network pipes, check connection stability
```

---

### #029 Network Interface Not Found

**DESCRIPTION:** Commands fail referencing an interface that does not exist.

**ROOT CAUSE:** Interface name changed (predictable naming) or driver not loaded.

**CAUSE:** Kernel update changed naming, driver missing, or hardware not detected.

**SOLUTION:**
```bash
ip link show                   # List all interfaces
lspci | grep -i network        # List network hardware
dmesg | grep eth               # Check kernel detection
modprobe <driver>              # Load network driver
nmcli device status            # NetworkManager device list
```

---

### #030 SSL Certificate Verify Failed

**DESCRIPTION:** curl/wget/application fails with SSL certificate verification error.

**ROOT CAUSE:** Certificate expired, self-signed, or CA bundle missing.

**CAUSE:** Expired cert, wrong hostname, or missing root CA.

**SOLUTION:**
```bash
openssl s_client -connect host:443  # Check certificate
curl -v https://host           # Verbose SSL debug
update-ca-certificates         # Update CA bundle (Debian)
update-ca-trust                # Update CA bundle (RHEL)
openssl x509 -in cert.pem -text -noout | grep -E "Not (Before|After)"
```

---

## Section 4: Authentication & User Errors

### #031 Authentication Failure

**DESCRIPTION:** Login fails with "Authentication failure" for password auth.

**ROOT CAUSE:** Wrong password, locked account, or PAM misconfiguration.

**CAUSE:** Incorrect credentials, expired password, or account locked.

**SOLUTION:**
```bash
faillock --user username       # Check failed login attempts
faillock --reset --user username  # Reset lock
passwd username                # Reset password
chage -l username              # Check password expiry
pam_tally2 --reset --user username  # Reset PAM tally (older systems)
```

---

### #032 sudo: User Not in Sudoers

**DESCRIPTION:** `sudo` fails with "user is not in the sudoers file".

**ROOT CAUSE:** User not added to sudoers configuration.

**CAUSE:** Missing sudoers entry or not in sudo/wheel group.

**SOLUTION:**
```bash
# As root:
usermod -aG sudo username      # Add to sudo group (Debian)
usermod -aG wheel username     # Add to wheel group (RHEL)
visudo                         # Edit sudoers safely
echo "username ALL=(ALL) ALL" >> /etc/sudoers.d/username
```

---

### #033 Account Locked

**DESCRIPTION:** Login fails; account is locked after failed attempts.

**ROOT CAUSE:** PAM pam_tally2 or pam_faillock locked the account.

**CAUSE:** Brute-force attempts or misconfigured lockout policy.

**SOLUTION:**
```bash
faillock --user username       # View lock status
faillock --reset --user username  # Unlock account
passwd -u username             # Unlock via passwd
usermod -U username            # Unlock user account
```

---

### #034 SSH: Too Many Authentication Failures

**DESCRIPTION:** SSH fails with "Too many authentication failures".

**ROOT CAUSE:** SSH client tried too many keys before password auth.

**CAUSE:** SSH agent offering many keys; MaxAuthTries exceeded.

**SOLUTION:**
```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/specific_key user@host
# Or in ~/.ssh/config:
# IdentitiesOnly yes
# IdentityFile ~/.ssh/specific_key
ssh-add -D                     # Clear SSH agent keys
```

---

### #035 su: Must Be Run from a Terminal

**DESCRIPTION:** `su` fails with "must be run from a terminal".

**ROOT CAUSE:** PAM requires a TTY for `su` authentication.

**CAUSE:** Running `su` from a script or non-TTY environment.

**SOLUTION:**
```bash
# Use sudo instead:
sudo -u username command
# Or allocate a TTY:
ssh -t user@host "su - otheruser"
# Check PAM config:
cat /etc/pam.d/su | grep tty
```

---

### #036 Group Does Not Exist

**DESCRIPTION:** Command fails because specified group is not found.

**ROOT CAUSE:** Group not created or typo in group name.

**CAUSE:** Missing group in `/etc/group`.

**SOLUTION:**
```bash
getent group groupname         # Check if group exists
groupadd groupname             # Create group
cat /etc/group | grep groupname
usermod -aG groupname username # Add user to group
```

---

### #037 User Does Not Exist

**DESCRIPTION:** Operation fails because the specified user account does not exist.

**ROOT CAUSE:** User not created or deleted.

**CAUSE:** Missing user in `/etc/passwd`.

**SOLUTION:**
```bash
getent passwd username         # Check if user exists
id username                    # Get user info
useradd -m -s /bin/bash username  # Create user
cat /etc/passwd | grep username
```

---

### #038 PAM System Error

**DESCRIPTION:** Authentication fails with "PAM system error" or "PAM: Authentication service cannot retrieve authentication info".

**ROOT CAUSE:** PAM configuration error or missing PAM module.

**CAUSE:** Misconfigured `/etc/pam.d/` files or missing `.so` library.

**SOLUTION:**
```bash
ls /lib/security/              # Check PAM modules
cat /etc/pam.d/sshd            # Check PAM config
authconfig --test              # Test auth config (RHEL)
pam-auth-update                # Update PAM (Debian)
journalctl | grep pam          # Check PAM logs
```

---

### #039 Kerberos kinit Failed

**DESCRIPTION:** `kinit` fails with "Preauthentication failed" or "Cannot contact KDC".

**ROOT CAUSE:** Wrong credentials, KDC unreachable, or clock skew.

**CAUSE:** Incorrect password, network issue, or time sync problem.

**SOLUTION:**
```bash
klist                          # Check existing tickets
kdestroy                       # Destroy existing tickets
kinit username@REALM           # Get new ticket
ntpdate -u <ntp-server>        # Sync time (Kerberos needs < 5min skew)
ping kdc.domain.com            # Check KDC reachability
```

---

### #040 LDAP: Can't Contact LDAP Server

**DESCRIPTION:** LDAP operations fail with "Can't contact LDAP server".

**ROOT CAUSE:** LDAP server unreachable or TLS handshake failure.

**CAUSE:** Network issue, wrong URI, or certificate problem.

**SOLUTION:**
```bash
ldapsearch -x -H ldap://server -b "dc=example,dc=com"
ping ldap-server               # Test connectivity
openssl s_client -connect ldap-server:636  # Test LDAPS
cat /etc/ldap/ldap.conf        # Check LDAP config
systemctl status slapd         # Check LDAP server status
```

---

## Section 5: Systemd & Service Errors

### #041 Unit Failed to Start

**DESCRIPTION:** `systemctl start service` fails; unit enters failed state.

**ROOT CAUSE:** Service binary crashed, configuration error, or dependency missing.

**CAUSE:** Wrong ExecStart path, permission issue, or missing dependency.

**SOLUTION:**
```bash
systemctl status service_name  # Check status and recent logs
journalctl -u service_name -n 50  # View service logs
systemctl cat service_name     # View unit file
systemd-analyze verify service_name.service  # Verify unit file
```

---

### #042 Failed to Enable Unit (File Exists)

**DESCRIPTION:** `systemctl enable` fails with "Failed to enable unit: File exists".

**ROOT CAUSE:** Symlink already exists or conflicts with another unit.

**CAUSE:** Previous partial enable or conflicting unit file.

**SOLUTION:**
```bash
ls -la /etc/systemd/system/service_name.service
rm /etc/systemd/system/service_name.service  # Remove stale symlink
systemctl daemon-reload
systemctl enable service_name
```

---

### #043 Job Timeout Exceeded

**DESCRIPTION:** Service fails to start within timeout; "Timeout waiting for response" in logs.

**ROOT CAUSE:** Service takes longer to start than `TimeoutStartSec`.

**CAUSE:** Slow initialization, dependency wait, or network timeout.

**SOLUTION:**
```bash
systemctl edit service_name    # Override unit settings
# Add in override:
# [Service]
# TimeoutStartSec=300
systemctl daemon-reload && systemctl restart service_name
```

---

### #044 Dependency Failed

**DESCRIPTION:** Service fails because a required dependency unit failed.

**ROOT CAUSE:** Required service (After=/Requires=) did not start successfully.

**CAUSE:** Dependency service has its own error or ordering issue.

**SOLUTION:**
```bash
systemctl list-dependencies service_name  # Show dependencies
systemctl status dependency_service  # Check failed dependency
journalctl -u dependency_service -n 30
systemctl reset-failed dependency_service
```

---

### #045 cgroup Resource Limit Exceeded

**DESCRIPTION:** Service killed with "cgroup memory limit exceeded" or OOM in journal.

**ROOT CAUSE:** Systemd unit's cgroup memory limit reached.

**CAUSE:** Service consuming more memory than configured limit.

**SOLUTION:**
```bash
systemctl show service_name | grep -i memory
systemctl edit service_name    # Add/increase limit:
# [Service]
# MemoryMax=2G
systemctl daemon-reload && systemctl restart service_name
```

---

### #046 ExecStart Not Found

**DESCRIPTION:** Service fails with "Executable path is not absolute" or binary not found.

**ROOT CAUSE:** ExecStart path in unit file is wrong or binary missing.

**CAUSE:** Incorrect path, binary not installed, or missing package.

**SOLUTION:**
```bash
systemctl cat service_name | grep ExecStart
which binary_name              # Find binary location
ls -la /path/to/binary         # Verify exists and executable
apt install package / yum install package  # Install if missing
```

---

### #047 journald: No Space for Journal

**DESCRIPTION:** journald stops accepting logs; "No space left on device" in syslog.

**ROOT CAUSE:** Journal directory at storage limit.

**CAUSE:** Low disk space or journal size limit too large.

**SOLUTION:**
```bash
journalctl --disk-usage        # Check journal size
journalctl --vacuum-size=1G    # Trim to 1GB
journalctl --vacuum-time=7d    # Keep only last 7 days
# Edit /etc/systemd/journald.conf:
# SystemMaxUse=500M
systemctl restart systemd-journald
```

---

### #048 Failed to Mount tmpfs

**DESCRIPTION:** Service or system fails to mount tmpfs filesystem.

**ROOT CAUSE:** tmpfs mount size exceeds available memory or wrong options.

**CAUSE:** Insufficient memory or incorrect mount options.

**SOLUTION:**
```bash
mount | grep tmpfs             # List tmpfs mounts
free -h                        # Check available memory
mount -t tmpfs -o size=512m tmpfs /mnt/tmpfs  # Mount with size limit
cat /proc/mounts | grep tmpfs
```

---

### #049 Service Still Running at Shutdown

**DESCRIPTION:** System shutdown hangs waiting for service to stop.

**ROOT CAUSE:** Service does not respond to SIGTERM within `TimeoutStopSec`.

**CAUSE:** Service ignores SIGTERM or takes too long to stop.

**SOLUTION:**
```bash
systemctl edit service_name    # Add:
# [Service]
# TimeoutStopSec=30
# KillMode=mixed
# KillSignal=SIGTERM
systemctl daemon-reload
```

---

### #050 Timer Unit Missed Activation

**DESCRIPTION:** Systemd timer unit did not fire at scheduled time.

**ROOT CAUSE:** System was off during scheduled window or timer misconfigured.

**CAUSE:** `OnCalendar` syntax error, system downtime, or `Persistent=false`.

**SOLUTION:**
```bash
systemctl list-timers          # Show all timers
systemctl status timer_name.timer
journalctl -u timer_name.service  # Check service logs
# Add to timer unit: Persistent=true
systemd-analyze calendar 'daily'  # Verify calendar syntax
```

---

## Section 6: Package Management Errors

### #051 dpkg: Dependency Problems

**DESCRIPTION:** `apt install` fails with "dpkg: dependency problems prevent configuration".

**ROOT CAUSE:** Required dependency not installed or version conflict.

**CAUSE:** Partial upgrade, held package, or conflicting packages.

**SOLUTION:**
```bash
apt-get install -f             # Fix broken dependencies
dpkg --configure -a            # Configure pending packages
apt-get autoremove             # Remove unneeded packages
dpkg -l | grep ^rc | awk '{print $2}' | xargs dpkg --purge
```

---

### #052 rpm: Failed Dependencies

**DESCRIPTION:** `rpm -i` or `yum install` fails with dependency errors.

**ROOT CAUSE:** Required RPM package not available or version mismatch.

**CAUSE:** Missing dependency in repository or conflicting versions.

**SOLUTION:**
```bash
yum deplist package            # Show dependencies
yum install --skip-broken package  # Skip broken deps
rpm -Va package                # Verify package integrity
yum clean all && yum makecache  # Refresh repo metadata
```

---

### #053 apt: Unable to Lock

**DESCRIPTION:** apt fails with "Could not get lock /var/lib/dpkg/lock".

**ROOT CAUSE:** Another apt/dpkg process is running or lock file stale.

**CAUSE:** Concurrent package operation or crashed previous apt session.

**SOLUTION:**
```bash
ps aux | grep -E "apt|dpkg"    # Find conflicting process
kill -9 <pid>                  # Kill if safe
rm /var/lib/dpkg/lock-frontend
rm /var/lib/dpkg/lock
rm /var/cache/apt/archives/lock
dpkg --configure -a
```

---

### #054 yum/dnf: No Package Found

**DESCRIPTION:** `yum install` or `dnf install` fails with "No package found".

**ROOT CAUSE:** Package not in any enabled repository.

**CAUSE:** Missing repository, package name typo, or EPEL not enabled.

**SOLUTION:**
```bash
yum search package_name        # Search repositories
yum repolist                   # List enabled repos
yum install epel-release       # Enable EPEL
dnf config-manager --enable repo_name  # Enable specific repo
```

---

### #055 pip: Could Not Find a Version

**DESCRIPTION:** `pip install` fails with "Could not find a version that satisfies the requirement".

**ROOT CAUSE:** Package not found in PyPI or version constraint unsatisfiable.

**CAUSE:** Typo in package name, wrong index, or incompatible Python version.

**SOLUTION:**
```bash
pip search package_name        # Search PyPI
pip install package_name --index-url https://pypi.org/simple/
python --version               # Check Python version compatibility
pip install "package>=1.0,<2.0"  # Specify version range
```

---

### #056 GPG Key Verification Failed

**DESCRIPTION:** Package installation fails with "GPG key verification failed" or "NO_PUBKEY".

**ROOT CAUSE:** Repository GPG key not imported or key expired.

**CAUSE:** Missing or expired signing key.

**SOLUTION:**
```bash
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys <KEY_ID>  # Import key
rpm --import /path/to/gpg-key  # Import RPM key
apt-get update --allow-unauthenticated  # Bypass temporarily
gpg --recv-keys <KEY_ID>       # Import GPG key
```

---

### #057 Repository Metadata Outdated

**DESCRIPTION:** Package manager reports "Metadata expired" or stale package lists.

**ROOT CAUSE:** Local repository cache is outdated.

**CAUSE:** Long time since last update or interrupted download.

**SOLUTION:**
```bash
apt-get update                 # Refresh apt cache
yum clean all && yum makecache # Refresh yum cache
dnf clean all && dnf makecache # Refresh dnf cache
apt-get clean                  # Clean downloaded packages
```

---

### #058 snap: Already Installed

**DESCRIPTION:** `snap install` fails with "snap is already installed".

**ROOT CAUSE:** Snap package already present on system.

**CAUSE:** Previous installation exists.

**SOLUTION:**
```bash
snap list                      # List installed snaps
snap refresh package_name      # Update existing snap
snap remove package_name       # Remove then reinstall
snap info package_name         # Check snap info
```

---

### #059 pip: Externally Managed Environment

**DESCRIPTION:** pip install fails with "error: externally-managed-environment" on newer systems.

**ROOT CAUSE:** Python environment is managed by system package manager.

**CAUSE:** PEP 668 — system Python protected from pip modifications.

**SOLUTION:**
```bash
python3 -m venv myenv          # Create virtual environment
source myenv/bin/activate      # Activate venv
pip install package_name       # Install in venv
# Or: pip install --break-system-packages package_name (not recommended)
```

---

### #060 Checksum Mismatch During Download

**DESCRIPTION:** Package installation fails with "checksum mismatch" or "hash sum mismatch".

**ROOT CAUSE:** Downloaded package corrupted or mirror serving wrong file.

**CAUSE:** Network corruption, MITM, or stale mirror cache.

**SOLUTION:**
```bash
apt-get clean && apt-get update  # Clear cache and retry
yum clean packages && yum install package  # Clear yum cache
# Change to different mirror in /etc/apt/sources.list or /etc/yum.repos.d/
sha256sum downloaded_file      # Manually verify checksum
```

---

## Section 7: Docker & Container Errors

### #061 Cannot Connect to Docker Daemon

**DESCRIPTION:** Docker commands fail with "Cannot connect to the Docker daemon".

**ROOT CAUSE:** Docker daemon not running or socket permission issue.

**CAUSE:** Docker service stopped or user not in docker group.

**SOLUTION:**
```bash
systemctl start docker         # Start Docker
systemctl status docker        # Check Docker status
usermod -aG docker $USER       # Add user to docker group
newgrp docker                  # Apply group without logout
ls -la /var/run/docker.sock    # Check socket permissions
```

---

### #062 Docker: No Space Left on Device

**DESCRIPTION:** Docker build or run fails with "no space left on device".

**ROOT CAUSE:** Docker's storage driver layer or overlay filesystem full.

**CAUSE:** Accumulated images, containers, volumes consuming disk.

**SOLUTION:**
```bash
docker system df               # Show Docker disk usage
docker system prune -a         # Remove unused resources
docker image prune -a          # Remove unused images
docker volume prune            # Remove unused volumes
df -h /var/lib/docker          # Check Docker directory
```

---

### #063 OCI Runtime: Permission Denied

**DESCRIPTION:** Container fails to start with "OCI runtime create failed: permission denied".

**ROOT CAUSE:** SELinux/AppArmor blocking container operations or wrong capabilities.

**CAUSE:** Security policy preventing container from accessing required resources.

**SOLUTION:**
```bash
docker run --privileged ...    # Run with full privileges (not recommended for prod)
docker run --security-opt label=disable ...  # Disable SELinux labeling
getenforce                     # Check SELinux mode
setenforce 0                   # Disable SELinux (temporary)
```

---

### #064 docker build: COPY Failed

**DESCRIPTION:** Docker build fails at COPY instruction with "no such file or directory".

**ROOT CAUSE:** Source file not present in build context or path wrong.

**CAUSE:** `.dockerignore` excluding file, wrong path, or missing file.

**SOLUTION:**
```bash
ls -la path/to/file            # Verify file exists
cat .dockerignore              # Check exclusions
docker build --no-cache .      # Rebuild without cache
# Fix COPY path in Dockerfile to be relative to build context
```

---

### #065 Container Exits with Code 137

**DESCRIPTION:** Container exits immediately with exit code 137.

**ROOT CAUSE:** Container process received SIGKILL (137 = 128 + 9).

**CAUSE:** OOM kill, Docker `stop` with timeout, or cgroup memory limit.

**SOLUTION:**
```bash
docker inspect <container> | grep -i "oomkilled"
docker stats                   # Monitor resource usage
docker run -m 512m ...         # Set memory limit
docker events                  # Check Docker events
journalctl -k | grep oom       # Check OOM killer in kernel logs
```

---

### #066 docker pull: Unauthorized

**DESCRIPTION:** `docker pull` fails with "unauthorized: authentication required".

**ROOT CAUSE:** Not logged in to registry or credentials expired.

**CAUSE:** Missing or expired registry credentials.

**SOLUTION:**
```bash
docker login registry.example.com  # Login to registry
cat ~/.docker/config.json      # Check stored credentials
docker logout && docker login  # Re-authenticate
kubectl create secret docker-registry ...  # For Kubernetes pulls
```

---

### #067 Kubernetes: CrashLoopBackOff

**DESCRIPTION:** Pod shows CrashLoopBackOff; container repeatedly crashes and restarts.

**ROOT CAUSE:** Container's main process exits with error; Kubernetes restarts with exponential backoff.

**CAUSE:** Application crash, missing config, wrong entrypoint, or OOM.

**SOLUTION:**
```bash
kubectl describe pod <pod-name>  # Check events and state
kubectl logs <pod-name> --previous  # Logs from crashed container
kubectl logs <pod-name> -c <container>  # Specific container logs
kubectl exec -it <pod-name> -- /bin/sh  # Debug interactively
```

---

### #068 Kubernetes: ImagePullBackOff

**DESCRIPTION:** Pod stuck in ImagePullBackOff; cannot pull container image.

**ROOT CAUSE:** Image not found, wrong tag, or registry authentication failure.

**CAUSE:** Typo in image name, private registry without pull secret, or image deleted.

**SOLUTION:**
```bash
kubectl describe pod <pod-name> | grep -A5 Events
kubectl get events --sort-by=.metadata.creationTimestamp
# Fix image name/tag in deployment
kubectl create secret docker-registry regcred --docker-server=... --docker-username=... --docker-password=...
```

---

### #069 docker network: Endpoint Exists

**DESCRIPTION:** Container fails to connect to network with "endpoint with name already exists".

**ROOT CAUSE:** Stale network endpoint from previous container not cleaned up.

**CAUSE:** Container crash left dangling endpoint.

**SOLUTION:**
```bash
docker network inspect <network>  # Check endpoints
docker network disconnect -f <network> <container>  # Force disconnect
docker network rm <network>    # Remove and recreate network
docker system prune            # Clean up stale resources
```

---

### #070 containerd: Failed to Create Shim

**DESCRIPTION:** Container fails to start with "failed to create shim" error.

**ROOT CAUSE:** containerd-shim binary missing or runc error.

**CAUSE:** Missing runtime binary, permission issue, or cgroup error.

**SOLUTION:**
```bash
which runc                     # Check runc is installed
runc --version                 # Verify runc works
systemctl restart containerd   # Restart containerd
journalctl -u containerd -n 50  # Check containerd logs
apt install containerd.io      # Reinstall containerd
```

---

## Section 8: Kernel & Boot Errors

### #071 Kernel Panic: Not Syncing

**DESCRIPTION:** System crashes with "Kernel panic - not syncing" message.

**ROOT CAUSE:** Unrecoverable kernel error — no init found, VFS corruption, or hardware fault.

**CAUSE:** Missing initramfs, corrupt root filesystem, or hardware failure.

**SOLUTION:**
```bash
# Boot from recovery media
# Rebuild initramfs:
mkinitcpio -p linux            # Arch Linux
update-initramfs -u            # Debian/Ubuntu
dracut --force                 # RHEL/CentOS
# Check dmesg for root cause
```

---

### #072 GRUB: Unknown Filesystem

**DESCRIPTION:** GRUB shows "error: unknown filesystem" at boot.

**ROOT CAUSE:** GRUB cannot read the filesystem where it's installed.

**CAUSE:** Filesystem changed, GRUB not updated, or disk UUID changed.

**SOLUTION:**
```bash
# Boot from live media, chroot:
mount /dev/sdXN /mnt
grub-install --root-directory=/mnt /dev/sdX
grub-mkconfig -o /mnt/boot/grub/grub.cfg
update-grub                    # Debian/Ubuntu
grub2-mkconfig -o /boot/grub2/grub.cfg  # RHEL
```

---

### #073 initramfs: Unable to Find Live Filesystem

**DESCRIPTION:** Boot drops to initramfs shell with "unable to find a live filesystem".

**ROOT CAUSE:** initramfs cannot locate root filesystem to mount.

**CAUSE:** Disk UUID changed, missing driver, or wrong root= parameter.

**SOLUTION:**
```bash
# From initramfs prompt:
ls /dev/sd*                    # Find disks
mount /dev/sdXN /root          # Try mounting manually
# Fix GRUB config with correct UUID:
blkid /dev/sdXN                # Get UUID
# Update /boot/grub/grub.cfg root=UUID=...
```

---

### #074 modprobe: Module Not Found

**DESCRIPTION:** `modprobe` fails with "Module not found in directory".

**ROOT CAUSE:** Kernel module not available for running kernel.

**CAUSE:** Module not installed for current kernel version or kernel update.

**SOLUTION:**
```bash
uname -r                       # Check kernel version
ls /lib/modules/$(uname -r)/   # Check modules directory
apt install linux-modules-extra-$(uname -r)  # Install extra modules
modprobe -v module_name        # Verbose module load
depmod -a                      # Rebuild module dependencies
```

---

### #075 Kernel NMI Watchdog: Soft Lockup

**DESCRIPTION:** Kernel logs "NMI watchdog: BUG: soft lockup - CPU#N stuck".

**ROOT CAUSE:** CPU core running kernel code without interruption for too long.

**CAUSE:** Driver bug, CPU frequency scaling issue, or VM overhead.

**SOLUTION:**
```bash
dmesg | grep -i "lockup\|NMI"
echo 0 > /proc/sys/kernel/nmi_watchdog  # Disable NMI watchdog
sysctl -w kernel.watchdog_thresh=30
# Check if VM: vmstat, check host CPU
cat /proc/cpuinfo | grep MHz  # Check CPU frequency
```

---

### #076 ACPI: Unsupported BusWidth

**DESCRIPTION:** Boot shows ACPI errors about "Unsupported BusWidth".

**ROOT CAUSE:** ACPI BIOS bug or incompatible ACPI tables.

**CAUSE:** Firmware bug in ACPI implementation.

**SOLUTION:**
```bash
# Add kernel parameter in GRUB:
# acpi=off or acpi=noirq
# Edit /etc/default/grub:
# GRUB_CMDLINE_LINUX="acpi=off"
update-grub && reboot
dmesg | grep -i acpi           # Review ACPI messages
```

---

### #077 dracut: Cannot Find Device

**DESCRIPTION:** dracut initramfs cannot find root device during boot.

**ROOT CAUSE:** Root device not available in initramfs or wrong UUID/label.

**CAUSE:** Wrong root= parameter, missing driver in initramfs, or disk not detected.

**SOLUTION:**
```bash
dracut --force --add-drivers "driver_name"  # Add driver to initramfs
dracut -v --force              # Rebuild with verbose output
cat /boot/grub2/grub.cfg | grep root  # Check root parameter
blkid                          # Verify disk UUID
```

---

### #078 EFI Boot Entry Not Found

**DESCRIPTION:** System fails to boot; UEFI shows no bootable entry.

**ROOT CAUSE:** EFI boot entry missing or EFI variables corrupted.

**CAUSE:** OS reinstall without updating EFI, firmware reset, or partition deleted.

**SOLUTION:**
```bash
efibootmgr -v                  # List EFI entries
# Boot from live media:
mount /dev/sdX1 /boot/efi      # Mount EFI partition
grub-install --target=x86_64-efi --efi-directory=/boot/efi
efibootmgr --create --disk /dev/sda --part 1 --label "Linux" --loader /EFI/ubuntu/grubx64.efi
```

---

### #079 Kernel SCSI Error

**DESCRIPTION:** Kernel logs SCSI errors: "SCSI error: return code = 0x08000002".

**ROOT CAUSE:** Storage device returning errors to SCSI layer.

**CAUSE:** Failing disk, bad cable, HBA issue, or timeout.

**SOLUTION:**
```bash
dmesg | grep -i "scsi\|sd[a-z]"
smartctl -a /dev/sda           # Check disk health
lsblk                          # List block devices
hdparm -I /dev/sda             # Device information
# Replace failing disk, check cables
```

---

### #080 Memory EDAC Error

**DESCRIPTION:** Kernel logs "EDAC MC0: 1 CE memory read error" or similar.

**ROOT CAUSE:** ECC memory correction event or uncorrectable memory error.

**CAUSE:** Failing RAM module, incorrect seating, or voltage issue.

**SOLUTION:**
```bash
dmesg | grep -i "edac\|mce\|memory error"
edac-util -s                   # Check EDAC status
mcelog --client                # Machine check errors
# Run memtest86+ to identify bad RAM
# Replace faulty DIMM
```

---

## Section 9: Storage & RAID Errors

### #081 LVM: Couldn't Find Device with UUID

**DESCRIPTION:** LVM fails to activate volume group with "Couldn't find device with uuid".

**ROOT CAUSE:** Physical volume (PV) disk not available or UUID changed.

**CAUSE:** Disk removed, not connected, or disk failure.

**SOLUTION:**
```bash
pvs                            # List physical volumes
vgscan --mknodes               # Rescan for VGs
pvscan                         # Scan for PVs
vgchange -ay                   # Activate all volume groups
lvdisplay                      # Show logical volumes
```

---

### #082 mdadm: ARRAY Failed to Assemble

**DESCRIPTION:** mdadm RAID array fails to assemble at boot.

**ROOT CAUSE:** Too many failed disks or superblock mismatch.

**CAUSE:** Disk failure, wrong component order, or metadata version mismatch.

**SOLUTION:**
```bash
mdadm --detail /dev/md0        # Show array details
mdadm --examine /dev/sdX       # Examine disk superblock
mdadm --assemble --scan        # Try auto-assemble
mdadm --assemble /dev/md0 /dev/sda /dev/sdb  # Manual assemble
cat /proc/mdstat               # Array status
```

---

### #083 XFS: Metadata I/O Error

**DESCRIPTION:** XFS logs "metadata I/O error" and may remount read-only.

**ROOT CAUSE:** Disk I/O error affecting XFS journal or metadata.

**CAUSE:** Hardware failure or filesystem corruption.

**SOLUTION:**
```bash
dmesg | grep -i "xfs\|I/O error"
xfs_repair /dev/sdXN           # Repair XFS (unmounted)
xfs_check /dev/sdXN            # Check filesystem
smartctl -a /dev/sdX           # Check disk health
xfs_metadump /dev/sdXN /tmp/meta.dump  # Preserve metadata for analysis
```

---

### #084 ext4: Journal Commit I/O Error

**DESCRIPTION:** ext4 logs "journal commit I/O error" and filesystem goes read-only.

**ROOT CAUSE:** I/O error during journal write.

**CAUSE:** Failing disk or bad block in journal area.

**SOLUTION:**
```bash
dmesg | grep -i "ext4\|journal"
e2fsck -f /dev/sdXN            # Force check (unmounted)
tune2fs -l /dev/sdXN | grep "Journal"  # Journal info
debugfs /dev/sdXN              # Interactive filesystem debugger
```

---

### #085 NFS: Stale File Handle

**DESCRIPTION:** NFS operations fail with "Stale file handle" (ESTALE).

**ROOT CAUSE:** File or directory was deleted/moved on server while client had it open.

**CAUSE:** Server-side path change, server restart, or filesystem export changed.

**SOLUTION:**
```bash
umount -l /mount/point         # Lazy unmount
mount | grep nfs               # Check NFS mounts
showmount -e nfs-server        # Show server exports
mount -t nfs server:/export /mnt  # Remount
systemctl restart nfs-client   # Restart NFS client
```

---

### #086 ZFS: Pool Faulted

**DESCRIPTION:** ZFS pool enters FAULTED state; I/O operations fail.

**ROOT CAUSE:** Too many disk failures exceed redundancy level.

**CAUSE:** Multiple disk failures or VDev errors.

**SOLUTION:**
```bash
zpool status                   # Check pool status
zpool status -v pool_name      # Verbose status
zpool clear pool_name          # Clear errors
zpool replace pool_name old_disk new_disk  # Replace failed disk
zpool scrub pool_name          # Run data scrub
```

---

### #087 LUKS: Failed to Open Device

**DESCRIPTION:** `cryptsetup luksOpen` fails with "Failed to open LUKS device".

**ROOT CAUSE:** Wrong passphrase, key file missing, or device not a LUKS container.

**CAUSE:** Incorrect passphrase or corrupt LUKS header.

**SOLUTION:**
```bash
cryptsetup isLuks -v /dev/sdXN  # Verify LUKS device
cryptsetup luksDump /dev/sdXN  # Show LUKS header info
cryptsetup luksHeaderBackup /dev/sdXN --header-backup-file luks-backup.img
cryptsetup luksOpen /dev/sdXN name  # Try opening with passphrase
```

---

### #088 iSCSI: Connection Closed

**DESCRIPTION:** iSCSI target connection drops with "connection closed" errors.

**ROOT CAUSE:** Network interruption, target timeout, or initiator misconfiguration.

**CAUSE:** Network instability, iSCSI daemon crash, or target session limit.

**SOLUTION:**
```bash
systemctl status iscsid        # Check initiator status
iscsiadm -m session            # List iSCSI sessions
iscsiadm -m discovery -t st -p target_ip  # Rediscover targets
iscsiadm -m node --login       # Login to all nodes
journalctl -u iscsid -n 50     # Check iSCSI logs
```

---

### #089 Multipath: Path Failed

**DESCRIPTION:** Multipath logs "path failed" or device shows degraded state.

**ROOT CAUSE:** One or more storage paths to LUN failed.

**CAUSE:** Cable failure, HBA issue, or storage controller problem.

**SOLUTION:**
```bash
multipath -ll                  # Show multipath status
multipathd show paths          # Detailed path info
multipath -v3                  # Verbose rescan
systemctl restart multipathd   # Restart multipath daemon
cat /etc/multipath.conf        # Check configuration
```

---

### #090 btrfs: Parent Transid Verify Failed

**DESCRIPTION:** btrfs logs "parent transid verify failed" on mount or access.

**ROOT CAUSE:** btrfs metadata inconsistency or incomplete transaction.

**CAUSE:** Unclean shutdown, write cache not flushed, or hardware error.

**SOLUTION:**
```bash
dmesg | grep btrfs
btrfs check /dev/sdXN          # Check filesystem
btrfs rescue zero-log /dev/sdXN  # Clear log tree
btrfs scrub start /mnt         # Scrub for errors
mount -o recovery /dev/sdXN /mnt  # Recovery mount
```

---

## Section 10: Security Errors

### #091 SELinux: AVC Denied

**DESCRIPTION:** Operations fail; `dmesg` or `/var/log/audit/audit.log` shows "avc: denied".

**ROOT CAUSE:** SELinux policy denying the operation.

**CAUSE:** Wrong file context, policy not updated, or new application behavior.

**SOLUTION:**
```bash
ausearch -m avc -ts recent     # Recent AVC denials
audit2allow -a                 # Suggest policy changes
audit2allow -a -M mypolicy     # Generate policy module
semodule -i mypolicy.pp        # Install policy module
restorecon -v /path/to/file    # Restore correct context
ls -Z /path/to/file            # Check SELinux context
```

---

### #092 AppArmor: Operation Not Permitted

**DESCRIPTION:** AppArmor blocks operation; `/var/log/syslog` shows "apparmor DENIED".

**ROOT CAUSE:** AppArmor profile denying the requested operation.

**CAUSE:** Profile too restrictive or new file/capability needed.

**SOLUTION:**
```bash
aa-status                      # Show AppArmor status
journalctl | grep apparmor     # Check denial messages
aa-complain /usr/sbin/daemon   # Set profile to complain mode
aa-logprof                     # Update profile from logs
aa-disable /etc/apparmor.d/profile  # Disable profile temporarily
```

---

### #093 Firewalld: ALREADY_ENABLED

**DESCRIPTION:** `firewall-cmd` returns "ALREADY_ENABLED" when adding rule.

**ROOT CAUSE:** Firewall rule already exists in the configuration.

**CAUSE:** Duplicate rule addition attempt.

**SOLUTION:**
```bash
firewall-cmd --list-all        # List current rules
firewall-cmd --query-service=http  # Check if service enabled
firewall-cmd --remove-service=http --permanent  # Remove if needed
firewall-cmd --add-service=http --permanent && firewall-cmd --reload
```

---

### #094 fail2ban: Already Banned

**DESCRIPTION:** fail2ban log shows IP being "already banned" repeatedly.

**ROOT CAUSE:** IP banned multiple times; not being cleaned from ban list properly.

**CAUSE:** findtime/bantime configuration issue or filter matching repeatedly.

**SOLUTION:**
```bash
fail2ban-client status         # Overall status
fail2ban-client status sshd    # Jail status
fail2ban-client set sshd unbanip <IP>  # Unban specific IP
cat /var/log/fail2ban.log | grep <IP>  # Check ban history
fail2ban-client restart        # Restart fail2ban
```

---

### #095 openssl: Certificate Expired

**DESCRIPTION:** SSL operations fail with "certificate has expired" or "certificate is not yet valid".

**ROOT CAUSE:** TLS certificate past its notAfter date.

**CAUSE:** Certificate renewal failure or wrong system clock.

**SOLUTION:**
```bash
openssl x509 -in cert.pem -text -noout | grep "Not After"
openssl s_client -connect host:443 | openssl x509 -noout -dates
# Renew certificate:
certbot renew --force-renewal   # Let's Encrypt
# Or generate new self-signed:
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
```

---

### #096 SSH: Host Key Verification Failed

**DESCRIPTION:** SSH fails with "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!"

**ROOT CAUSE:** Server's host key changed (server reinstalled, IP reassigned).

**CAUSE:** Server rebuild, IP reuse, or potential MITM attack.

**SOLUTION:**
```bash
ssh-keygen -R hostname         # Remove old key
ssh-keygen -R ip_address       # Remove by IP
# Verify new key fingerprint via out-of-band method
ssh-keyscan -H hostname >> ~/.ssh/known_hosts  # Add new key
```

---

### #097 GPG: No Public Key

**DESCRIPTION:** GPG verification fails with "No public key" or "Can't check signature".

**ROOT CAUSE:** GPG key not in local keyring.

**CAUSE:** Key not imported or key server unreachable.

**SOLUTION:**
```bash
gpg --recv-keys <KEY_ID>       # Import from default keyserver
gpg --keyserver hkp://keyserver.ubuntu.com --recv-keys <KEY_ID>
gpg --import /path/to/key.asc  # Import from file
gpg --list-keys                # List imported keys
```

---

### #098 auditd: Backlog Limit Exceeded

**DESCRIPTION:** auditd logs "audit: backlog limit exceeded" and events are lost.

**ROOT CAUSE:** Audit event queue full; kernel cannot write events fast enough.

**CAUSE:** High system activity generating many audit events.

**SOLUTION:**
```bash
auditctl -s                    # Show audit status
# Edit /etc/audit/auditd.conf:
# backlog_limit = 8192
# Edit /etc/audit/rules.d/audit.rules:
# -b 8192
service auditd restart
auditctl -b 8192               # Set backlog limit live
```

---

### #099 rkhunter: Suspicious File Found

**DESCRIPTION:** rkhunter scan reports suspicious files or configuration warnings.

**ROOT CAUSE:** rkhunter detected files matching known rootkit signatures or unusual permissions.

**CAUSE:** Legitimate software flagged, actual compromise, or outdated rkhunter database.

**SOLUTION:**
```bash
rkhunter --update              # Update database
rkhunter --check               # Run full check
rkhunter --propupd             # Update file properties after legitimate changes
cat /var/log/rkhunter.log      # Review findings
# Investigate each finding before concluding it is false positive
```

---

### #100 chroot: Failed to Run Command

**DESCRIPTION:** `chroot` fails with "failed to run command: No such file or directory".

**ROOT CAUSE:** Shell or required libraries not available in chroot environment.

**CAUSE:** Incomplete chroot setup — missing binaries or dynamic libraries.

**SOLUTION:**
```bash
# Copy required binaries and libs into chroot:
cp /bin/bash /mnt/chroot/bin/
ldd /bin/bash                  # Find required libraries
cp /lib/x86_64-linux-gnu/libc.so.6 /mnt/chroot/lib/x86_64-linux-gnu/
# Use arch-chroot (Arch) or chroot with bind mounts:
mount --bind /proc /mnt/chroot/proc
mount --bind /sys /mnt/chroot/sys
mount --bind /dev /mnt/chroot/dev
```

---

## Section 11: Advanced Networking Errors

### #101 iptables: Invalid Source/Destination

**DESCRIPTION:** iptables rule rejected with "Invalid source/destination specification".

**ROOT CAUSE:** Incorrect CIDR notation or invalid IP address in rule.

**CAUSE:** Syntax error in IP/mask, e.g., `192.168.1.0/255` instead of `192.168.1.0/24`.

**SOLUTION:**
```bash
iptables -A INPUT -s 192.168.1.0/24 -j ACCEPT  # Correct CIDR
ipcalc 192.168.1.0/24          # Verify network notation
iptables -L -n --line-numbers  # List current rules
iptables-save                  # Export current rules
```

---

### #102 tc: Cannot Find Device

**DESCRIPTION:** `tc` traffic control commands fail with "Cannot find device".

**ROOT CAUSE:** Network interface name specified does not exist.

**CAUSE:** Wrong interface name or interface not up.

**SOLUTION:**
```bash
ip link show                   # List interfaces
tc qdisc show                  # Show queuing disciplines
ip link set eth0 up            # Bring interface up
tc qdisc add dev eth0 root fq_codel  # Add qdisc to correct interface
```

---

### #103 nftables: No Such File or Directory

**DESCRIPTION:** nft command fails loading ruleset with "No such file or directory".

**ROOT CAUSE:** nftables ruleset file path wrong or nft not installed.

**CAUSE:** Missing ruleset file or incorrect path.

**SOLUTION:**
```bash
which nft                      # Check nft is installed
nft list ruleset               # Show current ruleset
nft -f /etc/nftables.conf      # Load from file
systemctl start nftables       # Start nftables service
ls /etc/nftables*              # Find configuration files
```

---

### #104 VPN: TLS Handshake Failed

**DESCRIPTION:** VPN connection fails with "TLS handshake failed" or certificate error.

**ROOT CAUSE:** Certificate mismatch, expired cert, or cipher incompatibility.

**CAUSE:** Expired CA cert, wrong CN/SAN, or incompatible TLS version.

**SOLUTION:**
```bash
# OpenVPN:
openvpn --verb 9 --config client.ovpn  # Debug verbosity
# Check certificate dates:
openssl x509 -in ca.crt -text -noout | grep -A2 "Validity"
# WireGuard: check keys match
wg showconf wg0                # Show WireGuard config
```

---

### #105 hostname: Name or Service Not Known

**DESCRIPTION:** Command fails resolving a hostname with "Name or service not known".

**ROOT CAUSE:** DNS cannot resolve the hostname.

**CAUSE:** Missing DNS entry, wrong search domain, or `/etc/hosts` missing entry.

**SOLUTION:**
```bash
dig hostname                   # DNS lookup
nslookup hostname              # Alternative lookup
cat /etc/resolv.conf           # Check DNS config
cat /etc/hosts                 # Check local hosts
getent hosts hostname          # NSS resolution
host hostname                  # Simple hostname lookup
```

---

### #106 Socket: Too Many Open Sockets

**DESCRIPTION:** Network operations fail with "Too many open files" for sockets.

**ROOT CAUSE:** Socket file descriptor limit reached.

**CAUSE:** Connection leak, high-concurrency application, or low ulimit.

**SOLUTION:**
```bash
ss -s                          # Socket statistics summary
lsof -i | wc -l               # Count open sockets
ulimit -n 65536                # Increase FD limit
sysctl -w net.core.somaxconn=65536  # Increase listen backlog
sysctl -w net.ipv4.tcp_max_syn_backlog=65536
```

---

### #107 NetworkManager: Device Not Managed

**DESCRIPTION:** NetworkManager shows interface as "unmanaged".

**ROOT CAUSE:** Interface set as unmanaged in NetworkManager config.

**CAUSE:** `/etc/NetworkManager/NetworkManager.conf` or udev rules marking it unmanaged.

**SOLUTION:**
```bash
nmcli device status            # Show device status
nmcli device set eth0 managed yes  # Set as managed
# Edit /etc/NetworkManager/NetworkManager.conf:
# [keyfile]
# unmanaged-devices=none
systemctl restart NetworkManager
```

---

### #108 DHCP: No Lease Obtained

**DESCRIPTION:** Network interface fails to get DHCP lease; falls back to APIPA or no IP.

**ROOT CAUSE:** DHCP server unreachable or no available leases.

**CAUSE:** DHCP server down, wrong VLAN, or exhausted IP pool.

**SOLUTION:**
```bash
dhclient -v eth0               # Verbose DHCP request
journalctl -u dhclient         # DHCP client logs
dhcping -s dhcp-server -c client_ip  # Test DHCP server
tcpdump -i eth0 port 67 or port 68  # Capture DHCP traffic
```

---

### #109 BGP: Hold Timer Expired

**DESCRIPTION:** BGP peer relationship drops with "Hold Timer Expired" error.

**ROOT CAUSE:** BGP keepalives not received within hold timer interval.

**CAUSE:** Network latency, CPU overload, or misconfigured timers.

**SOLUTION:**
```bash
# In FRR/Quagga:
show ip bgp summary            # BGP peer status
show ip bgp neighbors <peer>   # Detailed peer info
# Increase hold time:
neighbor <peer> timers 10 30   # keepalive 10, hold 30
# Check CPU usage and network path to peer
```

---

### #110 WireGuard: Handshake Did Not Complete

**DESCRIPTION:** WireGuard tunnel not establishing; "Latest handshake" shows never or old time.

**ROOT CAUSE:** Firewall blocking UDP port, wrong keys, or endpoint unreachable.

**CAUSE:** Firewall blocking WireGuard port (51820), key mismatch, or routing issue.

**SOLUTION:**
```bash
wg show                        # Show WireGuard status
# Check firewall:
iptables -L | grep 51820
ufw allow 51820/udp
# Verify public keys match on both ends
wg showconf wg0                # Full config
tcpdump -i eth0 udp port 51820  # Capture WireGuard traffic
```

---

## Section 12: Programming & Build Errors

### #111 gcc: Undefined Reference to Symbol

**DESCRIPTION:** Compilation fails with "undefined reference to `function`" at linker stage.

**ROOT CAUSE:** Symbol declared but not linked; missing library.

**CAUSE:** Missing `-l` flag, wrong library order, or missing package.

**SOLUTION:**
```bash
gcc -o output file.c -lm -lpthread  # Link required libraries
ldd binary                     # Check library dependencies
ldconfig -p | grep libname     # Find installed library
apt install libname-dev        # Install development library
pkg-config --libs --cflags libname  # Get compiler/linker flags
```

---

### #112 cmake: Could Not Find Package

**DESCRIPTION:** cmake fails with "Could NOT find Package (missing: PACKAGE_LIBRARIES)".

**ROOT CAUSE:** Required package/library not installed or not in cmake search path.

**CAUSE:** Missing development package or non-standard install location.

**SOLUTION:**
```bash
apt install libpackage-dev     # Install development package
cmake -DCMAKE_PREFIX_PATH=/custom/path ..  # Set search path
find / -name "PackageConfig.cmake" 2>/dev/null  # Find package config
cmake --debug-find-pkg Package .  # Debug package finding
```

---

### #113 python: ImportError No Module

**DESCRIPTION:** Python fails with "ImportError: No module named 'module_name'".

**ROOT CAUSE:** Python package not installed in active environment.

**CAUSE:** Package not installed, wrong Python version, or wrong virtualenv.

**SOLUTION:**
```bash
pip list | grep module_name    # Check if installed
pip install module_name        # Install package
python -m pip install module_name  # Use specific Python
which python && python --version  # Verify Python in use
source venv/bin/activate && pip install module_name
```

---

### #114 java: ClassNotFoundException

**DESCRIPTION:** Java application throws `java.lang.ClassNotFoundException`.

**ROOT CAUSE:** Required class not in classpath at runtime.

**CAUSE:** Missing JAR in classpath, wrong classpath configuration.

**SOLUTION:**
```bash
java -cp ".:lib/*:dependency.jar" MainClass  # Set classpath
# Maven: check pom.xml dependencies
mvn dependency:resolve         # Resolve dependencies
mvn dependency:tree            # Show dependency tree
# Check JAVA_HOME and java version:
java -version && echo $JAVA_HOME
```

---

### #115 go build: Cannot Find Package

**DESCRIPTION:** `go build` fails with "cannot find package" error.

**ROOT CAUSE:** Package not in GOPATH or module not downloaded.

**CAUSE:** Missing `go get`, wrong module path, or GOPATH issue.

**SOLUTION:**
```bash
go env GOPATH GOMODCACHE       # Check Go environment
go get package/path            # Download package
go mod tidy                    # Clean up go.mod
go mod download                # Download all dependencies
export GOPATH=$HOME/go         # Set GOPATH
```

---

### #116 make: No Rule to Make Target

**DESCRIPTION:** `make` fails with "No rule to make target 'target', needed by 'all'".

**ROOT CAUSE:** Makefile doesn't have a rule for the specified target.

**CAUSE:** Typo in target name, missing Makefile, or missing source file.

**SOLUTION:**
```bash
make -n target                 # Dry run to see what would run
cat Makefile | grep "target:"  # Find target definition
ls -la Makefile                # Verify Makefile exists
make -f correct_makefile target  # Specify correct Makefile
```

---

### #117 ruby: gem Not Found

**DESCRIPTION:** Ruby application fails with "Gem::LoadError: cannot load such file".

**ROOT CAUSE:** Required gem not installed.

**CAUSE:** gem not in Gemfile, bundle not run, or wrong Ruby version.

**SOLUTION:**
```bash
gem list | grep gem_name       # Check if installed
gem install gem_name           # Install gem
bundle install                 # Install from Gemfile
rbenv version && ruby -v       # Check Ruby version
bundle exec ruby app.rb        # Run with correct gems
```

---

### #118 node: Cannot Find Module

**DESCRIPTION:** Node.js fails with "Cannot find module 'module_name'".

**ROOT CAUSE:** npm package not installed in node_modules.

**CAUSE:** `npm install` not run or package missing from package.json.

**SOLUTION:**
```bash
npm install                    # Install dependencies
npm install module_name --save  # Install and save to package.json
ls node_modules | grep module_name  # Verify installation
node -e "require('module_name')"  # Test require
npm ci                         # Clean install from package-lock.json
```

---

### #119 bash: Command Not Found

**DESCRIPTION:** Shell returns "command: command not found" error.

**ROOT CAUSE:** Binary not installed or not in PATH.

**CAUSE:** Package not installed, wrong PATH, or typo.

**SOLUTION:**
```bash
which command_name             # Find in PATH
echo $PATH                     # Check current PATH
type command_name              # Show command type
find / -name command_name 2>/dev/null  # Locate binary
apt install package_name / yum install package_name  # Install
export PATH=$PATH:/new/path    # Add to PATH
```

---

### #120 Ansible: UNREACHABLE

**DESCRIPTION:** Ansible task fails with "UNREACHABLE! host is unreachable".

**ROOT CAUSE:** Cannot SSH to target host.

**CAUSE:** Host down, SSH port blocked, wrong credentials, or wrong IP.

**SOLUTION:**
```bash
ping target_host               # Test connectivity
ssh -v user@target_host        # Test SSH manually
ansible -m ping target_host    # Ansible connectivity test
ansible-playbook -vvv playbook.yml  # Verbose output
# Check inventory file for correct host/user settings
cat ~/.ansible/ansible.cfg     # Check Ansible config
```

---

## Section 13: Database Errors

### #121 MySQL: Too Many Connections

**DESCRIPTION:** MySQL returns "ERROR 1040: Too many connections".

**ROOT CAUSE:** Active connections reached `max_connections` limit.

**CAUSE:** Connection leak, insufficient limit, or connection pool misconfigured.

**SOLUTION:**
```sql
SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';
SET GLOBAL max_connections = 500;
SHOW PROCESSLIST;
-- Kill idle connections
```
```bash
# In /etc/mysql/mysql.conf.d/mysqld.cnf:
# max_connections = 500
systemctl restart mysql
```

---

### #122 PostgreSQL: Role Does Not Exist

**DESCRIPTION:** `psql` fails with "FATAL: role 'username' does not exist".

**ROOT CAUSE:** PostgreSQL role (user) not created.

**CAUSE:** User not created in PostgreSQL or wrong username.

**SOLUTION:**
```bash
sudo -u postgres psql          # Connect as postgres superuser
```
```sql
\du                            -- List roles
CREATE ROLE username WITH LOGIN PASSWORD 'password';
CREATE DATABASE dbname OWNER username;
GRANT ALL PRIVILEGES ON DATABASE dbname TO username;
```

---

### #123 Redis: NOAUTH Authentication Required

**DESCRIPTION:** Redis commands fail with "NOAUTH Authentication required".

**ROOT CAUSE:** Redis configured with password but client not authenticating.

**CAUSE:** Missing `requirepass` in client or wrong password.

**SOLUTION:**
```bash
redis-cli -a password ping     # Authenticate
redis-cli AUTH password        # Authenticate in session
# In redis.conf:
# requirepass yourpassword
# In application connection string: redis://:password@host:6379
```

---

### #124 MongoDB: Not Primary or Slave

**DESCRIPTION:** Write operations fail with "not primary or slave ok=false".

**ROOT CAUSE:** Attempting writes on a MongoDB replica set secondary.

**CAUSE:** Connected to wrong node or primary stepped down.

**SOLUTION:**
```javascript
rs.status()                    // Check replica set status
rs.isMaster()                  // Check if primary
db.getMongo().setReadPref("primary")  // Force primary reads
// Use connection string with replicaSet parameter:
// mongodb://host1,host2,host3/db?replicaSet=rsName
```

---

### #125 SQLite: Database Is Locked

**DESCRIPTION:** SQLite returns "database is locked" or "SQLITE_BUSY" error.

**ROOT CAUSE:** Another process has exclusive lock on the SQLite database.

**CAUSE:** Concurrent access without WAL mode or long-running transaction.

**SOLUTION:**
```bash
lsof | grep database.db        # Find processes accessing DB
fuser database.db              # Show PIDs using file
# In application: use WAL mode
sqlite3 database.db "PRAGMA journal_mode=WAL;"
# Set busy timeout:
sqlite3 database.db ".timeout 30000"
```

---

### #126 Elasticsearch: master_not_discovered_exception

**DESCRIPTION:** Elasticsearch fails with "master_not_discovered_exception" and cluster is RED.

**ROOT CAUSE:** Cluster cannot elect a master node; split-brain or quorum lost.

**CAUSE:** More than half of master-eligible nodes down or network partition.

**SOLUTION:**
```bash
curl -X GET "localhost:9200/_cluster/health?pretty"
curl -X GET "localhost:9200/_cat/nodes?v"
# Check logs:
journalctl -u elasticsearch -n 100
# Verify cluster.initial_master_nodes in elasticsearch.yml
# Check network connectivity between nodes
```

---

### #127 MySQL: Table Is Crashed

**DESCRIPTION:** MySQL returns "ERROR 1194: Table is marked as crashed".

**ROOT CAUSE:** MyISAM table index/data files are inconsistent.

**CAUSE:** Server crash during write or improper shutdown.

**SOLUTION:**
```sql
REPAIR TABLE tablename;
CHECK TABLE tablename;
-- For MyISAM:
```
```bash
mysqlcheck -u root -p --repair database_name tablename
myisamchk --recover /var/lib/mysql/db/tablename.MYI
```

---

### #128 PostgreSQL: Could Not Connect to Server

**DESCRIPTION:** `psql` fails with "could not connect to server: Connection refused".

**ROOT CAUSE:** PostgreSQL server not running or listening on wrong address.

**CAUSE:** PostgreSQL service stopped, port blocked, or wrong host in pg_hba.conf.

**SOLUTION:**
```bash
systemctl status postgresql    # Check PostgreSQL status
systemctl start postgresql     # Start if stopped
ss -tlnp | grep 5432          # Check if listening
cat /etc/postgresql/*/main/pg_hba.conf  # Check HBA rules
cat /etc/postgresql/*/main/postgresql.conf | grep listen_addresses
```

---

### #129 RabbitMQ: Channel Closed with Error

**DESCRIPTION:** AMQP channel closes unexpectedly with an error code.

**ROOT CAUSE:** Protocol error — wrong queue/exchange declaration or permission issue.

**CAUSE:** Queue declare mismatch, wrong vhost, or insufficient permissions.

**SOLUTION:**
```bash
rabbitmqctl list_queues        # List queues
rabbitmqctl list_users         # List users
rabbitmqctl list_permissions   # Check permissions
rabbitmqctl set_permissions -p / user ".*" ".*" ".*"  # Grant permissions
# Check RabbitMQ logs for specific error code
journalctl -u rabbitmq-server -n 50
```

---

### #130 Cassandra: WriteTimeoutException

**DESCRIPTION:** Cassandra client receives `WriteTimeoutException`.

**ROOT CAUSE:** Write did not receive acknowledgment from required number of replicas within timeout.

**CAUSE:** Node failure, network delay, or high write load.

**SOLUTION:**
```bash
nodetool status                # Check node status
nodetool tpstats               # Thread pool statistics
# In application: reduce consistency level or increase timeout
# Check for dropped messages:
nodetool tpstats | grep -i drop
# Check Cassandra logs:
tail -f /var/log/cassandra/system.log
```

---

## Section 14: CI/CD & Automation Errors

### #131 Jenkins: Executor Not Available

**DESCRIPTION:** Jenkins builds queue indefinitely; no executor available.

**ROOT CAUSE:** All executors busy or agents offline.

**CAUSE:** Too many concurrent builds, agent disconnected, or insufficient resources.

**SOLUTION:**
```
# Jenkins UI: Manage Jenkins > Nodes
# Check agent status and reconnect if offline
# Increase number of executors on agent
# Add new agent node
# Use declarative pipeline with specific agent labels
```
```groovy
pipeline {
    agent { label 'linux-agent' }
    // ...
}
```

---

### #132 GitLab CI: Runner Not Available

**DESCRIPTION:** GitLab CI pipeline stuck waiting for runner; "Waiting for runner to pick up this job".

**ROOT CAUSE:** No registered runner matches job requirements.

**CAUSE:** Runner offline, wrong tags, or runner at capacity.

**SOLUTION:**
```bash
gitlab-runner status           # Check runner status
gitlab-runner list             # List registered runners
gitlab-runner start            # Start runner service
# Check .gitlab-ci.yml tags match runner tags
# Register new runner:
gitlab-runner register --url https://gitlab.com/ --registration-token TOKEN
```

---

### #133 Terraform: Error Acquiring State Lock

**DESCRIPTION:** Terraform fails with "Error acquiring the state lock" on backend.

**ROOT CAUSE:** Another Terraform operation holds the state lock, or stale lock exists.

**CAUSE:** Previous Terraform run crashed without releasing lock.

**SOLUTION:**
```bash
terraform force-unlock LOCK_ID  # Force unlock (use carefully)
# For S3/DynamoDB backend, check DynamoDB for stale lock:
aws dynamodb scan --table-name terraform-state-lock
aws dynamodb delete-item --table-name terraform-state-lock --key '{"LockID":{"S":"bucket/path.tfstate"}}'
```

---

### #134 Ansible: Error in Vault Password

**DESCRIPTION:** Ansible fails with "ERROR! Decryption failed (no vault secrets were found)".

**ROOT CAUSE:** Vault password not provided or wrong password.

**CAUSE:** Missing `--ask-vault-pass`, wrong vault file, or wrong password.

**SOLUTION:**
```bash
ansible-playbook playbook.yml --ask-vault-pass  # Prompt for password
ansible-playbook playbook.yml --vault-password-file ~/.vault_pass
# Check vault file:
ansible-vault view encrypted_file.yml
# Rekey vault:
ansible-vault rekey encrypted_file.yml
```

---

### #135 Helm: Chart Not Found

**DESCRIPTION:** `helm install` fails with "Error: chart not found" or "no repositories configured".

**ROOT CAUSE:** Helm chart repository not added or chart doesn't exist.

**CAUSE:** Missing `helm repo add`, wrong chart name, or repo not updated.

**SOLUTION:**
```bash
helm repo list                 # List repositories
helm repo add stable https://charts.helm.sh/stable  # Add repo
helm repo update               # Update repo cache
helm search repo chart_name    # Search for chart
helm install release chart_name --version x.y.z
```

---

### #136 kubectl: Error Forbidden

**DESCRIPTION:** kubectl returns "Error from server (Forbidden): pods is forbidden".

**ROOT CAUSE:** ServiceAccount or user lacks RBAC permission for the operation.

**CAUSE:** Missing ClusterRole/Role binding for the user or service account.

**SOLUTION:**
```bash
kubectl auth can-i list pods --as=user -n namespace  # Check permissions
kubectl get rolebindings,clusterrolebindings -A | grep username
# Create RBAC:
kubectl create clusterrolebinding user-admin --clusterrole=admin --user=username
kubectl describe clusterrole cluster-admin  # Check role permissions
```

---

### #137 GitHub Actions: Secret Not Found

**DESCRIPTION:** GitHub Actions workflow fails accessing secret; shows empty value.

**ROOT CAUSE:** Secret not defined in repository or organization settings.

**CAUSE:** Typo in secret name, secret not set, or wrong scope.

**SOLUTION:**
```yaml
# In workflow, verify secret name matches exactly:
- run: echo "SECRET=${{ secrets.MY_SECRET }}"
# Check: Settings > Secrets and variables > Actions
# For org secrets: ensure repo has access to org secret
# Secrets are not available in forks by default
```

---

### #138 SonarQube: Quality Gate Failed

**DESCRIPTION:** CI pipeline fails because SonarQube quality gate did not pass.

**ROOT CAUSE:** Code metrics (coverage, bugs, vulnerabilities) below thresholds.

**CAUSE:** New bugs/vulnerabilities introduced or test coverage decreased.

**SOLUTION:**
```bash
# Check SonarQube dashboard for specific failures
# Fix code issues reported
# Update quality gate thresholds if appropriate:
# SonarQube UI > Quality Gates > Conditions
# Run analysis with debug:
mvn sonar:sonar -X
sonar-scanner --debug
```

---

### #139 Packer: Error Waiting for SSH

**DESCRIPTION:** Packer build fails with "Error waiting for SSH to become available".

**ROOT CAUSE:** Packer cannot SSH into the provisioned instance.

**CAUSE:** Wrong SSH user, key, timeout, or firewall blocking port 22.

**SOLUTION:**
```json
{
  "ssh_username": "ubuntu",
  "ssh_private_key_file": "~/.ssh/id_rsa",
  "ssh_timeout": "20m",
  "ssh_handshake_attempts": 20
}
```
```bash
packer build -debug template.json  # Debug mode (pauses for inspection)
# Check security group/firewall allows SSH
# Verify SSH key matches instance key pair
```

---

### #140 ArgoCD: Application Out of Sync

**DESCRIPTION:** ArgoCD shows application as "OutOfSync" and won't auto-sync.

**ROOT CAUSE:** Live cluster state diverged from Git repository definition.

**CAUSE:** Manual kubectl changes, failed sync, or Helm value drift.

**SOLUTION:**
```bash
argocd app get app-name        # Get app status
argocd app diff app-name       # Show differences
argocd app sync app-name       # Force sync
argocd app sync app-name --force  # Force sync with replace
# Check sync policy in ArgoCD app:
# automated: {prune: true, selfHeal: true}
```

---

## Section 15: Performance & Observability Errors

### #141 perf: Permission Denied (perf_event_paranoid)

**DESCRIPTION:** `perf` fails with "Permission denied" when run as non-root.

**ROOT CAUSE:** `kernel.perf_event_paranoid` restricts perf access.

**CAUSE:** Default kernel setting prevents unprivileged perf use.

**SOLUTION:**
```bash
cat /proc/sys/kernel/perf_event_paranoid  # Check current value
sysctl -w kernel.perf_event_paranoid=1   # Allow user profiling
sysctl -w kernel.perf_event_paranoid=-1  # Full access (development only)
# Or run with sudo:
sudo perf stat ./program
```

---

### #142 strace: Attach Operation Not Permitted

**DESCRIPTION:** `strace -p <pid>` fails with "attach: ptrace(PTRACE_SEIZE): Operation not permitted".

**ROOT CAUSE:** ptrace scope restrictions or running without root.

**CAUSE:** `kernel.yama.ptrace_scope` > 0 prevents attaching to other processes.

**SOLUTION:**
```bash
cat /proc/sys/kernel/yama/ptrace_scope  # Check scope
sysctl -w kernel.yama.ptrace_scope=0   # Allow ptrace
sudo strace -p <pid>           # Run with sudo
# Or: run strace as same user as target process
```

---

### #143 Prometheus: Many-to-Many Matching Not Allowed

**DESCRIPTION:** PromQL query fails with "many-to-many matching not allowed".

**ROOT CAUSE:** Binary operation matches multiple time series on both sides without explicit grouping.

**CAUSE:** Missing `on()` or `group_left()/group_right()` in vector matching.

**SOLUTION:**
```promql
# Add grouping modifier:
metric_a * on(label) group_left() metric_b

# Or use ignoring() to exclude specific labels:
metric_a * ignoring(instance) group_left() metric_b

# Use sum() to aggregate first:
sum by (job) (metric_a) * sum by (job) (metric_b)
```

---

### #144 Grafana: No Data Source Found

**DESCRIPTION:** Grafana dashboard shows "No data source found" or panels show no data.

**ROOT CAUSE:** Data source not configured or connection failing.

**CAUSE:** Data source not added, wrong URL, or auth issue.

**SOLUTION:**
```bash
# Grafana UI: Configuration > Data Sources
# Add/verify Prometheus data source:
# URL: http://prometheus:9090
# Test connection with "Save & Test"
# Check Grafana logs:
journalctl -u grafana-server -n 50
# Verify Prometheus is accessible from Grafana:
curl http://prometheus:9090/api/v1/query?query=up
```

---

### #145 tcpdump: No Suitable Device Found

**DESCRIPTION:** `tcpdump` fails with "tcpdump: no suitable device found".

**ROOT CAUSE:** No network interface available or insufficient permissions.

**CAUSE:** Running without root, no interfaces, or wrong interface name.

**SOLUTION:**
```bash
sudo tcpdump -D                # List available interfaces (need sudo)
ip link show                   # List interfaces
sudo tcpdump -i eth0 -n        # Capture on specific interface
sudo tcpdump -i any -n         # Capture on all interfaces
tcpdump --list-interfaces      # Alternative listing
```

---

### #146 valgrind: Mismatched Free/Delete

**DESCRIPTION:** Valgrind reports "Mismatched free() / delete / delete []" error.

**ROOT CAUSE:** Memory allocated with one method freed with incompatible method.

**CAUSE:** `malloc` paired with `delete`, or `new[]` with `delete` instead of `delete[]`.

**SOLUTION:**
```bash
valgrind --leak-check=full --track-origins=yes ./program
# Fix in code: match allocation/deallocation
# malloc -> free
# new -> delete
# new[] -> delete[]
# Use AddressSanitizer for faster detection:
gcc -fsanitize=address -g -o program program.c
```

---

### #147 sar: Cannot Open /var/log/sa/saXX

**DESCRIPTION:** `sar` fails with "Cannot open /var/log/sa/saXX: No such file or directory".

**ROOT CAUSE:** sysstat data collection not running or saXX file not yet created for that date.

**CAUSE:** sysstat service not enabled, `sa1` cron not running, or wrong date specified.

**SOLUTION:**
```bash
systemctl enable --now sysstat  # Enable sysstat
systemctl status sysstat        # Check status
ls /var/log/sa/                # List available sa files
sar -A                          # Today's stats
# Force data collection:
/usr/lib/sysstat/sa1 1 1       # Run sa1 manually
```

---

### #148 gdb: No Symbol Table Loaded

**DESCRIPTION:** gdb shows "No symbol table is loaded" when trying to debug.

**ROOT CAUSE:** Binary compiled without debug symbols.

**CAUSE:** Missing `-g` flag at compilation.

**SOLUTION:**
```bash
# Recompile with debug symbols:
gcc -g -O0 -o program program.c  # Debug build
g++ -g -O0 -o program program.cpp
# Check if binary has symbols:
file program                   # Shows "with debug_info" if yes
objdump --syms program | head  # List symbols
nm program                     # Another way to list symbols
```

---

### #149 iostat: Device Not Found in /proc/diskstats

**DESCRIPTION:** `iostat` shows no data for a device or device missing from output.

**ROOT CAUSE:** Device not registered in kernel disk statistics.

**CAUSE:** Device unmounted, driver not loaded, or virtual device not reporting stats.

**SOLUTION:**
```bash
cat /proc/diskstats            # Raw disk stats
lsblk                          # List block devices
iostat -d -x 1                 # Extended disk stats
iostat /dev/sda 1              # Stats for specific device
dmesg | grep sd                # Kernel disk detection
```

---

### #150 systemd-analyze: Permission Denied

**DESCRIPTION:** `systemd-analyze` fails with "Failed to connect to bus: Permission denied".

**ROOT CAUSE:** Trying to analyze system bus as non-root user.

**CAUSE:** System-wide analysis requires root; user session may work differently.

**SOLUTION:**
```bash
sudo systemd-analyze           # Analyze system boot (requires root)
systemd-analyze --user         # Analyze user session
sudo systemd-analyze blame     # Show services slowing boot
sudo systemd-analyze critical-chain  # Show critical boot path
sudo systemd-analyze plot > boot.svg  # Generate boot chart
```

---

## Quick Reference Summary

| Section | Errors | Key Tools |
|---------|--------|-----------|
| Filesystem & Disk | #001–#010 | `df`, `fsck`, `smartctl`, `blkid` |
| Process & Memory | #011–#020 | `free`, `top`, `dmesg`, `ulimit` |
| Networking | #021–#030 | `ss`, `ping`, `traceroute`, `dig` |
| Authentication | #031–#040 | `faillock`, `id`, `visudo`, `getent` |
| Systemd/Service | #041–#050 | `systemctl`, `journalctl`, `systemd-analyze` |
| Package Management | #051–#060 | `apt`, `yum`, `pip`, `dpkg` |
| Docker/Container | #061–#070 | `docker`, `kubectl`, `crictl` |
| Kernel/Boot | #071–#080 | `dmesg`, `dracut`, `grub-install` |
| Storage/RAID | #081–#090 | `lvm`, `mdadm`, `zpool`, `cryptsetup` |
| Security | #091–#100 | `audit2allow`, `aa-status`, `faillock` |
| Advanced Networking | #101–#110 | `iptables`, `nft`, `wg`, `nmcli` |
| Programming/Build | #111–#120 | `gcc`, `cmake`, `pip`, `go`, `npm` |
| Database | #121–#130 | `mysql`, `psql`, `redis-cli`, `nodetool` |
| CI/CD/Automation | #131–#140 | `jenkins`, `gitlab-runner`, `terraform`, `helm` |
| Performance/Observability | #141–#150 | `perf`, `strace`, `valgrind`, `sar` |

---

*DevOps Shack — Linux Troubleshooting Guide 2026 Edition*
