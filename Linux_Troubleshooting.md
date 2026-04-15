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

---

# Sample Outputs — All 150 Errors

> What you actually see in the terminal when each error occurs and when you run the fix commands.

---

## Section 1: Filesystem & Disk Errors — Sample Outputs

### #001 No Space Left on Device

**Error seen:**
```
$ touch newfile.txt
touch: cannot touch 'newfile.txt': No space left on device

$ docker build .
error: failed to solve: failed to create overlay: no space left on device
```

**Diagnosis:**
```
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   50G     0 100% /         ← 100% full!
/dev/sdb1       200G  120G   80G  60% /data
tmpfs           7.8G  512M  7.3G   7% /dev/shm

$ du -sh /* 2>/dev/null | sort -rh | head -5
18G  /var
12G  /home
 8G  /opt
 4G  /tmp
 2G  /usr

$ du -sh /var/* | sort -rh | head -5
15G  /var/log           ← logs consuming 15G!
2G   /var/lib
512M /var/cache
```

**Fix output:**
```
$ journalctl --vacuum-size=500M
Vacuuming done, freed 14.5G of archived journals from /var/log/journal/...

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   36G   14G  73% /         ← free space recovered
```

---

### #002 Read-Only Filesystem

**Error seen:**
```
$ echo "test" > /var/log/app.log
-bash: /var/log/app.log: Read-only file system

$ systemctl restart nginx
Job for nginx.service failed. See 'journalctl -xe' for details.
Failed to write PID file: Read-only file system
```

**Diagnosis:**
```
$ dmesg | grep -i "read-only\|remount\|error" | tail -5
[123456.789] EXT4-fs error (device sda1): ext4_journal_check_start:61: Detected aborted journal
[123456.790] EXT4-fs (sda1): Remounting filesystem read-only
[123456.791] EXT4-fs error (device sda1): ext4_find_entry:1455: inode #2: comm kworker: reading directory lblock 0

$ mount | grep sda1
/dev/sda1 on / type ext4 (ro,relatime,errors=remount-ro)   ← ro = read-only!
```

**Fix output:**
```
$ fsck -y /dev/sda1
fsck from util-linux 2.37.2
e2fsck 1.46.5 (30-Dec-2021)
/dev/sda1: recovering journal
Pass 1: Checking inodes, blocks, and sizes
Pass 2: Checking directory structure
Pass 3: Checking directory connectivity
Pass 4: Checking reference counts
Pass 5: Checking group summary information
/dev/sda1: 48721/3276800 files (0.1% non-contiguous), 892341/13107200 blocks

$ mount -o remount,rw /
$ mount | grep sda1
/dev/sda1 on / type ext4 (rw,relatime)   ← rw = read-write restored
```

---

### #003 No Inodes Left

**Error seen:**
```
$ touch newfile.txt
touch: cannot touch 'newfile.txt': No space left on device

$ df -h       ← disk looks fine?
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   20G   30G  40% /    ← only 40% disk used but writes fail!
```

**Diagnosis:**
```
$ df -i
Filesystem      Inodes   IUsed   IFree IUse% Mounted on
/dev/sda1      3276800 3276800       0  100% /    ← 100% inodes used!
/dev/sdb1      6553600  123456 6430144    2% /data

$ find /var/spool/postfix -type f | wc -l
2847291    ← 2.8 million queued mail files!

$ find /tmp -type f | wc -l
489234
```

**Fix output:**
```
$ find /var/spool/postfix/deferred -type f -delete
$ find /tmp -type f -mtime +1 -delete

$ df -i
Filesystem      Inodes   IUsed   IFree IUse% Mounted on
/dev/sda1      3276800  124521 3152279    4% /   ← inodes recovered
```

---

### #004 Permission Denied

**Error seen:**
```
$ cat /etc/shadow
cat: /etc/shadow: Permission denied

$ ./deploy.sh
bash: ./deploy.sh: Permission denied

$ sudo cat /var/log/auth.log
sudo: unable to open /var/log/auth.log: Permission denied
```

**Diagnosis:**
```
$ ls -la /etc/shadow
-rw-r----- 1 root shadow 1234 Jan 15 10:30 /etc/shadow
              ↑ group=shadow, others have no permission

$ ls -la deploy.sh
-rw-r--r-- 1 deploy deploy 2048 Jan 15 10:30 deploy.sh
 ↑ no execute bit!

$ id
uid=1001(john) gid=1001(john) groups=1001(john)   ← not in shadow group
```

**Fix output:**
```
$ chmod +x deploy.sh
$ ls -la deploy.sh
-rwxr-xr-x 1 deploy deploy 2048 Jan 15 10:30 deploy.sh

$ usermod -aG shadow john
$ id john
uid=1001(john) gid=1001(john) groups=1001(john),42(shadow)
```

---

### #005 Too Many Open Files

**Error seen:**
```
$ java -jar app.jar
java.io.IOException: Too many open files
    at java.io.FileInputStream.open(Native Method)

$ nginx: [emerg] open() "/var/log/nginx/access.log" failed (24: Too many open files)
```

**Diagnosis:**
```
$ ulimit -n
1024     ← very low default limit

$ lsof -p $(pgrep java) | wc -l
1028     ← exceeded the 1024 limit

$ cat /proc/sys/fs/file-nr
35421    0    2097152
# currently open / always 0 / system max
```

**Fix output:**
```
$ ulimit -n 65536
$ ulimit -n
65536

$ echo "* soft nofile 65536" >> /etc/security/limits.conf
$ echo "* hard nofile 65536" >> /etc/security/limits.conf
$ echo "fs.file-max = 2097152" >> /etc/sysctl.conf
$ sysctl -p
fs.file-max = 2097152
```

---

### #006 Disk Quota Exceeded

**Error seen:**
```
$ cp bigfile.tar.gz /home/john/
cp: error writing '/home/john/bigfile.tar.gz': Disk quota exceeded

$ scp file.zip john@server:/home/john/
john@server's password:
scp: /home/john/file.zip: Disk quota exceeded
```

**Diagnosis:**
```
$ quota -u john
Disk quotas for user john (uid 1001):
     Filesystem  blocks   quota   limit   grace   files   quota   limit   grace
      /dev/sda1   5120*   5120    6144   6days    1234    2000    2500

$ repquota -a
*** Report for user quotas on device /dev/sda1
Block grace time: 7days; Inode grace time: 7days
                        Block limits                File limits
User            used    soft    hard  grace    used  soft  hard  grace
----------------------------------------------------------------------
john      --   5120*   5120    6144  6days    1234  2000  2500
```

**Fix output:**
```
$ edquota -u john
# Change soft=10240 hard=12288

$ quota -u john
     Filesystem  blocks   quota   limit   grace   files   quota   limit   grace
      /dev/sda1   5120   10240   12288            1234    2000    2500
```

---

### #007 No Such File or Directory (ENOENT)

**Error seen:**
```
$ cat /etc/app/config.yaml
cat: /etc/app/config.yaml: No such file or directory

$ python3 app.py
FileNotFoundError: [Errno 2] No such file or directory: '/var/run/app.pid'

$ ls -la /usr/bin/node
lrwxrwxrwx 1 root root 21 Jan 15 /usr/bin/node -> /usr/bin/nodejs
$ node --version
-bash: /usr/bin/node: No such file or directory   ← broken symlink!
```

**Diagnosis:**
```
$ file /usr/bin/node
/usr/bin/node: broken symbolic link to /usr/bin/nodejs

$ readlink -f /usr/bin/node
/usr/bin/nodejs   ← target doesn't exist

$ find / -name "nodejs" 2>/dev/null
/usr/bin/nodejs18    ← installed as different name
```

**Fix output:**
```
$ ln -sf /usr/bin/nodejs18 /usr/bin/node
$ node --version
v18.19.0
```

---

### #008 Input/Output Error

**Error seen:**
```
$ ls /mnt/data
ls: reading directory '/mnt/data': Input/output error

$ cp file.txt /mnt/backup/
cp: error writing '/mnt/backup/file.txt': Input/output error

$ dmesg | tail -5
[98234.123] blk_update_request: I/O error, dev sdb, sector 1234567
[98234.124] Buffer I/O error on dev sdb1, logical block 617283, async page read
[98234.125] EXT4-fs error (device sdb1): ext4_find_entry:1455: inode #2: reading directory lblock 0
```

**Diagnosis:**
```
$ smartctl -a /dev/sdb
SMART overall-health self-assessment test result: FAILED!
Drive failure expected in less than 24 hours. SAVE ALL DATA.

197 Current_Pending_Sector  0x0032   100   100   000    Old_age   Always       -       234
198 Offline_Uncorrectable   0x0030   100   100   000    Old_age   Offline      -       189
↑ 234 pending bad sectors, 189 uncorrectable — disk is failing!
```

**Action:**
```
# Immediately backup all data:
$ rsync -av /mnt/data/ /backup/emergency/ --ignore-errors

# Check bad blocks:
$ badblocks -sv /dev/sdb
Checking blocks 0 to 976773167
Checking for bad blocks (read-only test): done
Pass completed, 234 bad blocks found.
```

---

### #009 Filesystem Corruption (fsck)

**Error seen:**
```
# At boot — system drops to emergency shell:
Welcome to emergency mode! After logging in, type "journalctl -xb" to view
system logs, "systemctl reboot" to reboot, "systemctl default" or ^D to
try again to boot into default mode.

[  15.234] EXT4-fs (sda1): mounted filesystem with ordered data mode. Opts: (null)
[  15.235] EXT4-fs error (device sda1): ext4_validate_block_bitmap:376: comm systemd-journal: bg 0: bad block bitmap checksum
```

**Diagnosis & Fix:**
```
# Boot from recovery/live media, then:
$ fsck -y /dev/sda1
fsck from util-linux 2.37.2
e2fsck 1.46.5
/dev/sda1 was not cleanly unmounted, check forced.
Pass 1: Checking inodes, blocks, and sizes
Pass 2: Checking directory structure
Pass 3: Checking directory connectivity
Pass 4: Checking reference counts
Pass 5: Checking group summary information

/dev/sda1: ***** FILE SYSTEM WAS MODIFIED *****
/dev/sda1: 23456/3276800 files (0.2% non-contiguous), 892341/13107200 blocks
```

---

### #010 Mount: Wrong Filesystem Type

**Error seen:**
```
$ mount /dev/sdb1 /mnt
mount: /mnt: wrong fs type, bad option, bad superblock on /dev/sdb1,
       missing codepage or helper program, or other error.

$ mount -t ext4 /dev/sdb1 /mnt
mount: /mnt: can't read superblock on /dev/sdb1.
```

**Diagnosis:**
```
$ file -s /dev/sdb1
/dev/sdb1: Linux rev 1.0 ext3 filesystem data (needs journal recovery) (large files)
             ↑ It's ext3, not ext4!

$ blkid /dev/sdb1
/dev/sdb1: UUID="a1b2c3d4" TYPE="ext3" PARTUUID="xyz123"
```

**Fix output:**
```
$ mount -t ext3 /dev/sdb1 /mnt
$ mount | grep sdb1
/dev/sdb1 on /mnt type ext3 (rw,relatime)   ← mounted successfully
```

---

## Section 2: Process & Memory Errors — Sample Outputs

### #011 Cannot Allocate Memory (ENOMEM)

**Error seen:**
```
$ ./myapp
bash: fork: Cannot allocate memory

$ docker run myimage
docker: Error response from daemon: OCI runtime create failed:
container_linux.go:380: starting container process caused: process_linux.go:545:
container init caused: rootfs_linux.go:76: creating /dev/... Cannot allocate memory.
```

**Diagnosis:**
```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            15Gi        14Gi       128Mi       1.2Gi       512Mi       234Mi
Swap:          2.0Gi       2.0Gi         0Bi                            ← swap exhausted!

$ top -bn1 | head -15
Tasks: 412 total,   2 running, 410 sleeping,   0 stopped,   8 zombie
%Cpu(s): 89.2 us,  5.3 sy,  0.0 ni,  3.2 id,  2.3 wa
MiB Mem:  15360.0 total,    128.4 free,  14345.2 used,    886.4 buff/cache
MiB Swap:  2048.0 total,      0.0 free,   2048.0 used.    234.1 avail Mem

  PID USER     %MEM    VSZ    RSS  COMMAND
 1234 java     45.2  8192m  6890m  java -jar app.jar  ← memory leak!
```

---

### #012 Segmentation Fault

**Error seen:**
```
$ ./myprogram
Segmentation fault (core dumped)

$ dmesg | tail -3
[12345.678] myprogram[1234]: segfault at 0 ip 00007f1234 sp 00007fff error 4 in myprogram[400000+1000]
             ↑ segfault at address 0 = null pointer dereference
```

**Diagnosis:**
```
$ ulimit -c unlimited
$ ./myprogram
Segmentation fault (core dumped)

$ gdb ./myprogram core
GNU gdb (Ubuntu 12.1)
Reading symbols from ./myprogram...
[New LWP 1234]
Core was generated by `./myprogram'.
Program terminated with signal SIGSEGV, Segmentation fault.
#0  0x00000000004011a3 in process_data (data=0x0) at main.c:47
47          printf("%s\n", data->name);   ← null pointer dereference at line 47!

(gdb) bt
#0  process_data (data=0x0) at main.c:47
#1  main () at main.c:23
```

---

### #013 OOM Killer Invoked

**Error seen:**
```
$ dmesg | grep -i oom
[98234.123] Out of memory: Kill process 1234 (java) score 892 or sacrifice child
[98234.124] Killed process 1234 (java) total-vm:8192000kB, anon-rss:7168000kB, file-rss:0kB
[98234.125] oom_reaper: reaped process 1234 (java), now anon-rss:0kB, file-rss:0kB

$ journalctl -k | grep -i "oom\|killed"
Jan 15 10:30:01 server kernel: Out of memory: Kill process 1234 (java) score 892
Jan 15 10:30:01 server kernel: Killed process 1234 (java)
```

**Diagnosis:**
```
$ cat /proc/1234/oom_score      # Before process is killed
892    ← very high score = high chance of being OOM-killed (max 1000)

$ cat /proc/1/oom_score_adj     # systemd — protected
-1000
```

**Fix output:**
```
# Protect critical process:
$ echo -1000 > /proc/$(pgrep nginx)/oom_score_adj
$ cat /proc/$(pgrep nginx)/oom_score
0    ← nginx now protected from OOM killer
```

---

### #014 Process Not Found

**Error seen:**
```
$ kill 9999
bash: kill: (9999) - No such process

$ systemctl status myapp
● myapp.service - My Application
     Loaded: loaded (/etc/systemd/system/myapp.service; enabled)
     Active: failed (Result: exit-code)
```

**Diagnosis:**
```
$ ps aux | grep myapp
john      1234  0.0  0.0  14436  1024 pts/0    S+   10:30   0:00 grep myapp
# Only grep shown — myapp not running

$ pgrep -la myapp
# (no output — process not found)

$ journalctl -u myapp --since "10 minutes ago"
Jan 15 10:25:01 server myapp[1230]: FATAL: Cannot connect to database
Jan 15 10:25:01 server systemd[1]: myapp.service: Main process exited with code=1
```

---

### #015 Resource Temporarily Unavailable (EAGAIN)

**Error seen:**
```
$ python3 -c "import subprocess; [subprocess.Popen(['sleep','1']) for _ in range(10000)]"
BlockingIOError: [Errno 11] Resource temporarily unavailable

$ fork() failed: Resource temporarily unavailable
```

**Diagnosis:**
```
$ ulimit -u
4096    ← max user processes

$ ps aux | grep john | wc -l
4098    ← exceeded the 4096 limit!

$ cat /proc/sys/kernel/pid_max
32768
```

**Fix output:**
```
$ echo "john soft nproc 65536" >> /etc/security/limits.conf
$ echo "john hard nproc 65536" >> /etc/security/limits.conf

# Verify (after re-login):
$ ulimit -u
65536
```

---

### #016 Process Killed (Signal 9)

**Error seen:**
```
$ dmesg | grep killed
[12345.678] Killed process 5678 (python3) total-vm:2048000kB anon-rss:1843200kB

$ echo $?   # After process is killed
137          ← 128 + 9 (SIGKILL) = 137
```

---

### #017 Zombie Process

**Error seen:**
```
$ ps aux | awk '$8 == "Z"'
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
john      1234  0.0  0.0      0     0 ?        Z    10:30   0:00 [myapp] <defunct>
john      1235  0.0  0.0      0     0 ?        Z    10:30   0:00 [myapp] <defunct>

$ ps -o ppid= -p 1234
1100    ← parent PID is 1100
```

**Fix:**
```
$ kill -SIGCHLD 1100    # Signal parent to reap children
$ ps aux | awk '$8 == "Z"'
# (no output — zombies cleared)
```

---

### #018 CPU Soft Lockup

**Error seen:**
```
$ dmesg | grep "soft lockup"
[98234.123] watchdog: BUG: soft lockup - CPU#2 stuck for 23s! [kworker:1234]
[98234.124] Modules linked in: xt_conntrack nf_conntrack nf_defrag_ipv6
[98234.125] CPU: 2 PID: 1234 Comm: kworker/2:1 Tainted: G        W
```

---

### #019 Load Average Too High

**Error seen:**
```
$ uptime
 10:30:01 up 5 days,  2:34,  3 users,  load average: 45.23, 42.11, 38.56
                                                       ↑ 45x the number of CPUs!
$ nproc
4    ← only 4 CPUs but load is 45!
```

**Diagnosis:**
```
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
38  12  204800  12345  45678 234567  234  567 45678  1234 8901 2345 45  8  2 45  0
↑ r=38 runnable, b=12 blocked on I/O, wa=45% CPU wait = I/O bottleneck

$ iostat -x 1 3
Device     r/s   w/s  rMB/s  wMB/s   %util
sda       234.5 567.8   45.6   89.2   99.8    ← disk at 100% utilization!
```

---

### #020 ulimit: Max User Processes Reached

**Error seen:**
```
$ ssh john@server
ssh_exchange_identification: Connection closed by remote host

# On server:
$ journalctl -u sshd | tail -3
Jan 15 10:30 sshd[1234]: error: fork: Resource temporarily unavailable
Jan 15 10:30 sshd[1234]: error: do_cleanup
```

**Diagnosis:**
```
$ ps aux | grep john | wc -l
4097    ← at the limit

$ cat /proc/sys/kernel/threads-max
32768
```

---

## Section 3: Networking Errors — Sample Outputs

### #021 Connection Refused (ECONNREFUSED)

**Error seen:**
```
$ curl http://10.0.0.50:8080
curl: (7) Failed to connect to 10.0.0.50 port 8080 after 0 ms: Connection refused

$ telnet 10.0.0.50 8080
Trying 10.0.0.50...
telnet: Unable to connect to remote host: Connection refused
```

**Diagnosis:**
```
$ ss -tlnp | grep 8080
(no output — nothing listening on 8080)

$ ss -tlnp
State    Recv-Q  Send-Q  Local Address:Port
LISTEN   0       128     0.0.0.0:22         users:(("sshd",pid=1234))
LISTEN   0       128     0.0.0.0:80         users:(("nginx",pid=5678))
LISTEN   0       128     127.0.0.1:8080     users:(("myapp",pid=9012))
                          ↑ listening on 127.0.0.1 only — not accessible remotely!
```

---

### #022 Connection Timed Out (ETIMEDOUT)

**Error seen:**
```
$ curl --connect-timeout 10 http://10.0.0.50:3000
curl: (28) Connection timed out after 10001 milliseconds

$ ssh john@10.0.0.50
ssh: connect to host 10.0.0.50 port 22: Connection timed out
```

**Diagnosis:**
```
$ traceroute 10.0.0.50
traceroute to 10.0.0.50, 30 hops max
 1  192.168.1.1   1.1 ms
 2  * * *          ← packets dropped here
 3  * * *
...
30  * * *          ← never reaches destination

$ iptables -L INPUT -n | grep 3000
DROP       tcp  --  0.0.0.0/0    0.0.0.0/0   tcp dpt:3000   ← found it!
```

---

### #023 Network Unreachable

**Error seen:**
```
$ ping 8.8.8.8
ping: connect: Network is unreachable

$ curl http://google.com
curl: (7) Failed to connect to google.com port 80 after 0 ms: Network is unreachable
```

**Diagnosis:**
```
$ ip route show
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.10
# No default route! 'default via x.x.x.x' line is missing

$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.1.10/24 brd 192.168.1.255 scope global eth0
```

**Fix output:**
```
$ ip route add default via 192.168.1.1
$ ip route show
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.10

$ ping -c 2 8.8.8.8
PING 8.8.8.8: 64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3 ms
2 packets transmitted, 2 received, 0% packet loss   ← fixed!
```

---

### #024 DNS Resolution Failure

**Error seen:**
```
$ curl https://api.example.com
curl: (6) Could not resolve host: api.example.com

$ ping google.com
ping: google.com: Name or service not known
```

**Diagnosis:**
```
$ cat /etc/resolv.conf
# (empty file or corrupted)

$ dig @8.8.8.8 google.com
;; ANSWER SECTION:
google.com.     300  IN  A  142.250.80.46   ← works with explicit DNS

$ systemctl status systemd-resolved
● systemd-resolved.service - Network Name Resolution
     Active: failed (Result: exit-code)   ← resolver crashed!
```

**Fix output:**
```
$ echo "nameserver 8.8.8.8" > /etc/resolv.conf
$ echo "nameserver 1.1.1.1" >> /etc/resolv.conf

$ ping -c 2 google.com
PING google.com (142.250.80.46) 56(84) bytes of data.
64 bytes from 142.250.80.46: icmp_seq=1 ttl=117 time=12.1 ms
```

---

### #025 SSH Connection Reset

**Error seen:**
```
$ ssh user@10.0.0.50
Connection to 10.0.0.50 closed by remote host.
Connection to 10.0.0.50 port 22 was reset.

# During active session:
Write failed: Broken pipe
```

**Diagnosis:**
```
$ ssh -v user@10.0.0.50 2>&1 | grep -i "timeout\|mtu\|reset"
debug1: client_loop: send disconnect: Broken pipe
```

**Fix (add to `~/.ssh/config`):**
```
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

---

### #026 Address Already in Use (EADDRINUSE)

**Error seen:**
```
$ python3 -m http.server 8080
OSError: [Errno 98] Address already in use

$ nginx -t && systemctl start nginx
nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)
```

**Diagnosis:**
```
$ ss -tlnp | grep 8080
LISTEN  0  128  0.0.0.0:8080  0.0.0.0:*  users:(("python3",pid=5678,fd=3))
                                                    ↑ PID 5678 using it

$ lsof -i :8080
COMMAND  PID  USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
python3 5678  john    3u  IPv4 123456      0t0  TCP *:8080 (LISTEN)
```

**Fix output:**
```
$ kill 5678
$ ss -tlnp | grep 8080
(no output — port free)

$ python3 -m http.server 8080
Serving HTTP on 0.0.0.0 port 8080 ...   ← now works
```

---

### #027–#030 (Networking)

**#027 iptables chain error:**
```
$ iptables -A INPUT -m connlimit --connlimit-above 10 -j REJECT
iptables: No chain/target/match by that name.

$ modprobe xt_connlimit
$ iptables -A INPUT -m connlimit --connlimit-above 10 -j REJECT
# (success — no output)
```

**#028 Broken pipe:**
```
$ curl http://10.0.0.50/largefile | process_data
curl: (23) Failed writing body (0 != 16384)
# process_data exited before curl finished writing
```

**#029 Network interface not found:**
```
$ ip link show eth0
Device "eth0" does not exist.

$ ip link show
2: enp3s0: <BROADCAST,MULTICAST,UP,LOWER_UP>   ← renamed to enp3s0!
```

**#030 SSL certificate verify failed:**
```
$ curl https://internal.company.com
curl: (60) SSL certificate problem: self-signed certificate in certificate chain

$ curl -v https://internal.company.com 2>&1 | grep "expire\|issuer\|subject"
*  subject: CN=internal.company.com
*  issuer: CN=Company Internal CA   ← self-signed internal CA not trusted
*  SSL certificate verify result: self-signed certificate in certificate chain (19)
```

---

## Section 4: Authentication & User Errors — Sample Outputs

### #031 Authentication Failure

**Error seen:**
```
$ ssh john@server
john@server's password:
Permission denied, please try again.
john@server's password:
Permission denied (publickey,password).

$ journalctl -u sshd | tail -5
Jan 15 10:30 sshd[1234]: Failed password for john from 192.168.1.10 port 54321 ssh2
Jan 15 10:30 sshd[1234]: Failed password for john from 192.168.1.10 port 54321 ssh2
Jan 15 10:30 sshd[1234]: Failed password for john from 192.168.1.10 port 54321 ssh2
Jan 15 10:30 sshd[1234]: error: maximum authentication attempts exceeded for john
```

**Diagnosis & Fix:**
```
$ faillock --user john
john:
When                Type  Source                                           Valid
2024-01-15 10:28:01 RHOST 192.168.1.10                                        V
2024-01-15 10:28:45 RHOST 192.168.1.10                                        V
2024-01-15 10:29:12 RHOST 192.168.1.10                                        V

$ faillock --reset --user john
$ passwd john    # Reset password
New password:
Retype new password:
passwd: password updated successfully
```

---

### #032 sudo: Not in Sudoers

**Error seen:**
```
$ sudo apt update
[sudo] password for john:
john is not in the sudoers file. This incident will be reported.

$ cat /var/log/auth.log | grep sudo
Jan 15 10:30 server sudo: john : user NOT in sudoers ; TTY=pts/0 ; USER=root ; COMMAND=/usr/bin/apt update
```

**Fix output:**
```
# As root:
$ usermod -aG sudo john
$ id john
uid=1001(john) gid=1001(john) groups=1001(john),27(sudo)

# Verify (re-login required or use newgrp):
$ sudo apt update
[sudo] password for john:
Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease
Reading package lists... Done   ← sudo now works!
```

---

### #033–#040 (Auth errors condensed)

**#033 Account locked:**
```
$ su - john
su: Authentication failure

$ passwd -S john
john L 2024-01-15 0 99999 7 -1   ← L = Locked!

$ passwd -u john
passwd: password expiry information changed.
$ passwd -S john
john P 2024-01-15 0 99999 7 -1   ← P = Password set (unlocked)
```

**#034 SSH too many auth failures:**
```
$ ssh -v john@server 2>&1 | tail -5
debug1: Offering public key: /home/john/.ssh/id_ed25519
debug1: Offering public key: /home/john/.ssh/id_rsa
debug1: Offering public key: /home/john/.ssh/id_ecdsa
Received disconnect from server port 22:2: Too many authentication failures
# Fix: ssh -o IdentitiesOnly=yes -i ~/.ssh/specific_key john@server
```

**#039 Kerberos kinit failed:**
```
$ kinit john@CORP.EXAMPLE.COM
kinit: Preauthentication failed while getting initial credentials

$ date
Tue Jan 15 10:30:00 UTC 2024
$ ssh kdc-server date
Tue Jan 15 15:35:00 UTC 2024   ← 5+ minute clock skew! Kerberos requires < 5 min

$ ntpdate -u pool.ntp.org
15 Jan 10:30:05 ntpdate[1234]: adjust time server 203.0.113.1 offset -0.305142 sec
$ kinit john@CORP.EXAMPLE.COM
Password for john@CORP.EXAMPLE.COM:   ← now works!
```

---

## Section 5: Systemd & Service Errors — Sample Outputs

### #041 Unit Failed to Start

**Error seen:**
```
$ systemctl start myapp
Job for myapp.service failed because the control process exited with error code.
See "systemctl status myapp.service" and "journalctl -xe" for details.

$ systemctl status myapp
● myapp.service - My Application
     Loaded: loaded (/etc/systemd/system/myapp.service; enabled)
     Active: failed (Result: exit-code) since Tue 2024-01-15 10:30:01 UTC
    Process: 1234 ExecStart=/usr/bin/myapp --config /etc/myapp/config.yaml (code=exited, status=1/FAILURE)
   Main PID: 1234 (code=exited, status=1/FAILURE)

$ journalctl -u myapp -n 10
Jan 15 10:30:01 server myapp[1234]: FATAL: config file not found: /etc/myapp/config.yaml
Jan 15 10:30:01 server systemd[1]: myapp.service: Main process exited, code=exited, status=1/FAILURE
```

**Fix output:**
```
$ cp /usr/share/myapp/config.yaml.example /etc/myapp/config.yaml
$ systemctl start myapp
$ systemctl status myapp
● myapp.service - My Application
     Active: active (running) since Tue 2024-01-15 10:30:15 UTC
   Main PID: 2345 (myapp)
```

---

### #042–#050 (Systemd condensed)

**#043 Job timeout:**
```
$ systemctl start slow-service
Job for slow-service.service failed.

$ journalctl -u slow-service | tail -3
Jan 15 10:30 systemd[1]: slow-service.service: Start operation timed out. Terminating.
Jan 15 10:30 systemd[1]: slow-service.service: Failed with result 'timeout'.
# Fix: systemctl edit slow-service → add TimeoutStartSec=300
```

**#047 journald no space:**
```
$ journalctl
-- Journal begins at Mon 2024-01-14
-- Dropped 1234 messages due to rate limiting

$ journalctl --disk-usage
Archived and active journals take up 8.0G in the filesystem.

$ journalctl --vacuum-size=1G
Vacuuming done, freed 7.0G of archived journals.

$ journalctl --disk-usage
Archived and active journals take up 1.0G in the filesystem.
```

**#050 Timer missed activation:**
```
$ systemctl list-timers backup.timer
NEXT                         LEFT     LAST                         PASSED  UNIT
Mon 2024-01-15 02:00:00 UTC  13h left Sun 2024-01-14 02:00:00 UTC  22h ago backup.timer

$ systemctl status backup.service
● backup.service
     Active: inactive (dead)
    Process: 9876 ExecStart=/usr/bin/backup.sh (code=exited, status=0/SUCCESS)
# Missed due to system being offline — fix: add Persistent=true to timer unit
```

---

## Section 6: Package Management — Sample Outputs

### #051 dpkg Dependency Problems

**Error seen:**
```
$ apt install mypackage
Reading package lists... Done
Building dependency tree
The following packages have unmet dependencies:
 mypackage : Depends: libfoo (>= 2.0) but 1.8 is to be installed
             Depends: libbar (= 3.1) but 3.2 is installed
E: Unable to correct problems, you have held broken packages.
```

**Fix output:**
```
$ apt-get install -f
The following packages will be REMOVED:
  conflicting-package
The following packages will be upgraded:
  libfoo
Do you want to continue? [Y/n] Y
Setting up libfoo (2.1) ...
Setting up mypackage (1.0) ...
Processing triggers for man-db ...
```

---

### #052–#060 (Package management condensed)

**#053 apt lock:**
```
$ apt install nginx
E: Could not get lock /var/lib/dpkg/lock-frontend.
E: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend),
   is another process using it?

$ ps aux | grep apt
root  1234  0.0  0.1  apt-get upgrade   ← another apt running

$ kill 1234
$ apt install nginx   ← retry after previous apt completes
```

**#055 pip version not found:**
```
$ pip install django==3.0.0
ERROR: Could not find a version that satisfies the requirement django==3.0.0
ERROR: No matching distribution found for django==3.0.0

$ python --version
Python 3.12.0   ← Django 3.0 doesn't support Python 3.12!

$ pip install django==4.2.0   ← use compatible version
Successfully installed django-4.2.0
```

**#059 pip externally managed:**
```
$ pip install requests
error: externally-managed-environment
This environment is externally managed. To install packages, use:
  apt install python3-requests
or create a virtual environment.

$ python3 -m venv myenv
$ source myenv/bin/activate
(myenv) $ pip install requests
Successfully installed requests-2.31.0
```

---

## Section 7: Docker & Container Errors — Sample Outputs

### #061 Cannot Connect to Docker Daemon

**Error seen:**
```
$ docker ps
Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
Is the docker daemon running?

$ docker info
ERROR: Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
```

**Diagnosis:**
```
$ systemctl status docker
● docker.service - Docker Application Container Engine
     Active: inactive (dead)

$ ls -la /var/run/docker.sock
ls: cannot access '/var/run/docker.sock': No such file or directory
```

**Fix output:**
```
$ systemctl start docker
$ systemctl status docker
● docker.service - Docker Application Container Engine
     Active: active (running) since Tue 2024-01-15 10:30:01 UTC

$ docker ps
CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
# (empty — no containers running but daemon is up)
```

---

### #062 Docker No Space Left

**Error seen:**
```
$ docker build -t myapp .
Step 5/12 : RUN npm install
 ---> Running in abc123def456
error: ENOSPC: no space left on device

$ docker pull ubuntu:22.04
no space left on device
```

**Diagnosis:**
```
$ docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          45        12        28.5GB    18.2GB (63%)
Containers      23        3         1.2GB     890MB
Local Volumes   18        5         4.5GB     3.1GB
Build Cache     -         -         6.8GB     6.8GB
```

**Fix output:**
```
$ docker system prune -a --volumes
WARNING! This will remove:
  - all stopped containers
  - all networks not used by at least one container
  - all images without at least one container associated to them
  - all volumes not used by at least one container
Are you sure you want to continue? [y/N] y
Deleted Containers: abc123...
Deleted Images: sha256:def456...
Total reclaimed space: 22.3GB   ← 22GB freed!

$ df -h /var/lib/docker
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   12G   38G  24% /   ← space restored
```

---

### #063–#070 (Container condensed)

**#067 CrashLoopBackOff:**
```
$ kubectl get pods
NAME                    READY   STATUS             RESTARTS   AGE
webapp-7d9f-xk2p9      0/1     CrashLoopBackOff   23         45m

$ kubectl logs webapp-7d9f-xk2p9 --previous
Error: ECONNREFUSED - connect ECONNREFUSED 10.96.0.1:5432
    at TCPConnectWrap.afterConnect [as oncomplete]
# App can't connect to postgres — check service name and namespace
```

**#068 ImagePullBackOff:**
```
$ kubectl get pods
NAME              READY   STATUS             RESTARTS
myapp-abc123      0/1     ImagePullBackOff   0

$ kubectl describe pod myapp-abc123 | grep -A5 Events
Events:
  Warning  Failed  10s  kubelet  Failed to pull image "myrepo/myapp:v2.0.0":
           rpc error: code = Unknown desc = failed to pull and unpack image:
           unexpected status code 401 Unauthorized
# Fix: kubectl create secret docker-registry regcred ...
```

**#070 containerd shim failed:**
```
$ docker run hello-world
docker: Error response from daemon: failed to create shim task:
OCI runtime create failed: runc create failed: unable to start container process:
error during container init: error mounting "/proc/cpuinfo" to rootfs at "/proc/cpuinfo":
mount /proc/cpuinfo:/proc/cpuinfo (via /proc/self/fd/6), flags: 0x5001: not a directory: unknown.

$ runc --version
runc version 1.1.12
$ systemctl restart containerd
$ docker run hello-world
Hello from Docker!   ← fixed after restart
```

---

## Section 8: Kernel & Boot Errors — Sample Outputs

### #071 Kernel Panic

**Error seen:**
```
[    5.234] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
[    5.235] CPU: 0 PID: 1 Comm: swapper/0
[    5.236] Call Trace:
[    5.237]  dump_stack+0x68/0x8b
[    5.238]  panic+0xf6/0x2cd
[    5.239]  mount_block_root+0x1e9/0x280
[    5.240] ---[ end Kernel panic - not syncing: VFS: Unable to mount root fs ]---
```

**Fix (from recovery media):**
```
$ mount /dev/sda1 /mnt
$ mount --bind /proc /mnt/proc
$ mount --bind /sys /mnt/sys
$ mount --bind /dev /mnt/dev
$ chroot /mnt

# Inside chroot — rebuild initramfs:
$ update-initramfs -u -k all
update-initramfs: Generating /boot/initrd.img-6.5.0-15-generic
$ exit
$ reboot
```

---

### #072–#080 (Kernel/Boot condensed)

**#072 GRUB unknown filesystem:**
```
grub> ls
(hd0) (hd0,gpt1) (hd0,gpt2)
grub> ls (hd0,gpt2)/
error: unknown filesystem.   ← GRUB can't read the partition

# Boot from live media:
$ grub-install --root-directory=/mnt /dev/sda
Installing for x86_64-efi platform.
Installation finished. No error reported.
$ update-grub
Generating grub configuration file ...
Found linux image: /boot/vmlinuz-6.5.0-15-generic
done
```

**#074 modprobe module not found:**
```
$ modprobe wireguard
modprobe: FATAL: Module wireguard not found in directory /lib/modules/6.5.0-15-generic

$ uname -r
6.5.0-15-generic

$ apt install linux-modules-extra-$(uname -r)
Setting up linux-modules-extra-6.5.0-15-generic ...

$ modprobe wireguard
$ lsmod | grep wireguard
wireguard              98304  0   ← loaded successfully!
```

---

## Section 9: Storage & RAID Errors — Sample Outputs

### #081 LVM UUID Not Found

**Error seen:**
```
$ vgchange -ay
  WARNING: Couldn't find device with uuid 'abc123-def4-5678-90ab-cdef12345678'.
  WARNING: VG myvg is missing PV with uuid abc123-...
  1 logical volume(s) in volume group "myvg" now active
```

**Diagnosis:**
```
$ pvs
  PV          VG   Fmt  Attr PSize   PFree
  /dev/sda2   myvg lvm2 a--  100.00g     0
  [unknown]   myvg lvm2 a-m  100.00g     0   ← missing PV!

$ vgscan
  Found volume group "myvg" using metadata type lvm2
```

---

### #082–#090 (Storage condensed)

**#082 mdadm ARRAY failed:**
```
$ cat /proc/mdstat
Personalities : [raid6] [raid5] [raid4]
md0 : inactive sda[0](S) sdb[1](S)
      ↑ inactive — failed to assemble

$ mdadm --detail /dev/md0
State : inactive
Active Devices : 0
Failed Devices : 2

$ mdadm --examine /dev/sda | grep "Array UUID"
Array UUID : abc123:def456:789012:345678

$ mdadm --assemble /dev/md0 --uuid=abc123:def456:789012:345678 /dev/sda /dev/sdb
mdadm: /dev/md0 has been started with 2 drives.

$ cat /proc/mdstat
md0 : active raid1 sdb[1] sda[0]
      ↑ now active!
```

**#086 ZFS pool faulted:**
```
$ zpool status
  pool: data
 state: FAULTED
status: One or more devices has been removed by the administrator.
  scan: scrub repaired 0B in 00:00:01 with 0 errors on Sun Jan 14 00:25:01 2024
config:
        NAME        STATE     READ WRITE CKSUM
        data        FAULTED      0     0     0
          sda       REMOVED      0     0     0   ← disk removed/failed!
          sdb       ONLINE       0     0     0

$ zpool replace data sda /dev/sdc    # Replace with new disk
$ zpool status
  pool: data
 state: ONLINE
  scan: resilvered 45.6G in 00:12:34 with 0 errors
        NAME        STATE     READ WRITE CKSUM
        data        ONLINE       0     0     0
          sdc       ONLINE       0     0     0   ← rebuilt!
          sdb       ONLINE       0     0     0
```

---

## Section 10: Security Errors — Sample Outputs

### #091 SELinux AVC Denied

**Error seen:**
```
$ systemctl start nginx
Job for nginx.service failed.

$ journalctl -u nginx | tail -5
Jan 15 10:30 nginx[1234]: nginx: [emerg] open() "/var/www/html/app" failed (13: Permission denied)

$ ausearch -m avc -ts recent
type=AVC msg=audit(1705312201.234:567): avc: denied { read } for pid=1234
comm="nginx" name="app" dev="sda1" ino=12345
scontext=system_u:system_r:httpd_t:s0
tcontext=user_u:object_r:user_home_t:s0   ← wrong SELinux context!
tclass=dir permissive=0
```

**Fix output:**
```
$ ls -Z /var/www/html/
system_u:object_r:user_home_t:s0 app   ← wrong type: user_home_t

$ chcon -R -t httpd_sys_content_t /var/www/html/app
$ ls -Z /var/www/html/
system_u:object_r:httpd_sys_content_t:s0 app   ← correct type

$ systemctl start nginx
$ systemctl status nginx
     Active: active (running)   ← fixed!
```

---

### #092–#100 (Security condensed)

**#092 AppArmor denied:**
```
$ journalctl | grep apparmor | tail -3
Jan 15 apparmor: DENIED operation="open" profile="/usr/sbin/mysqld"
  name="/data/mysql/custom.cnf" pid=1234 comm="mysqld"
  requested_mask="r" denied_mask="r" fsuid=999 ouid=0

$ aa-complain /usr/sbin/mysqld
Setting /usr/sbin/mysqld to complain mode.
$ systemctl restart mysql
$ aa-logprof     # Update profile based on logged denials
$ aa-enforce /usr/sbin/mysqld
```

**#095 Certificate expired:**
```
$ curl https://api.example.com
curl: (60) SSL certificate problem: certificate has expired

$ openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -dates
notBefore=Jan  1 00:00:00 2023 GMT
notAfter=Jan  1 00:00:00 2024 GMT   ← expired Jan 1st!

$ certbot renew --force-renewal
Attempting to renew cert (api.example.com) from ...
Congratulations, all renewals succeeded:
  /etc/letsencrypt/live/api.example.com/fullchain.pem (success)
$ systemctl reload nginx
```

**#096 SSH host key changed:**
```
$ ssh john@10.0.0.50
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!  @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING A MITM ATTACK!
Host key for 10.0.0.50 has changed and you have requested strict checking.
Add correct host key in /home/john/.ssh/known_hosts to get rid of this message.
Offending ECDSA key in /home/john/.ssh/known_hosts:15

$ ssh-keygen -R 10.0.0.50
# Host 10.0.0.50 found: line 15
/home/john/.ssh/known_hosts updated.

$ ssh john@10.0.0.50
The authenticity of host '10.0.0.50' can't be established.
ECDSA key fingerprint is SHA256:abc123xyz789...
Are you sure you want to continue connecting (yes/no)? yes
```

---

## Section 11: Advanced Networking — Sample Outputs

### #101–#110 (Condensed)

**#104 VPN TLS handshake failed:**
```
$ openvpn --config client.ovpn
TLS Error: TLS handshake failed
TLS Error: TLS object -> incoming plaintext read error
SIGUSR1[soft,tls-error] received, process restarting

$ openssl x509 -in ca.crt -noout -dates
notBefore=Jan  1 00:00:00 2022 GMT
notAfter=Jan  1 00:00:00 2024 GMT   ← CA cert expired!
```

**#107 NetworkManager device unmanaged:**
```
$ nmcli device status
DEVICE  TYPE      STATE      CONNECTION
eth0    ethernet  unmanaged  --          ← unmanaged!
lo      loopback  unmanaged  --

$ nmcli device set eth0 managed yes
$ nmcli device status
DEVICE  TYPE      STATE      CONNECTION
eth0    ethernet  connected  Wired connection 1   ← now managed!
```

**#110 WireGuard handshake not completing:**
```
$ wg show
interface: wg0
  public key: abc123...
  private key: (hidden)
  listening port: 51820

peer: xyz789...
  endpoint: 203.0.113.1:51820
  allowed ips: 10.8.0.0/24
  latest handshake: (none)     ← never handshaked!
  transfer: 0 B received, 1.23 KiB sent

$ tcpdump -i eth0 udp port 51820
# (no traffic returned from peer = firewall blocking)

$ # On remote server:
$ iptables -I INPUT -p udp --dport 51820 -j ACCEPT
$ wg show
peer: xyz789...
  latest handshake: 2 seconds ago   ← handshake completed!
  transfer: 1.34 KiB received, 1.23 KiB sent
```

---

## Section 12: Programming & Build Errors — Sample Outputs

### #111–#120 (Condensed)

**#111 gcc undefined reference:**
```
$ gcc -o myapp myapp.c
/usr/bin/ld: myapp.o: in function 'main':
myapp.c:(.text+0x1a): undefined reference to 'sqrt'
/usr/bin/ld: myapp.c:(.text+0x2e): undefined reference to 'pow'
collect2: error: ld returned 1 exit status

$ gcc -o myapp myapp.c -lm    # Link math library
$ ./myapp
Result: 4.000000   ← works!
```

**#113 python ImportError:**
```
$ python3 app.py
Traceback (most recent call last):
  File "app.py", line 3, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'

$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install pandas
Successfully installed pandas-2.1.4 numpy-1.26.3
(venv) $ python3 app.py   ← works!
```

**#118 node cannot find module:**
```
$ node app.js
Error: Cannot find module 'express'
Require stack:
- /app/app.js

$ ls node_modules/
(no express directory)

$ npm install
added 62 packages in 3.4s

$ node app.js
Server running on port 3000   ← works!
```

**#120 Ansible UNREACHABLE:**
```
$ ansible all -m ping
server01 | UNREACHABLE! => {
    "changed": false,
    "msg": "Failed to connect to the host via ssh: ssh: connect to host server01 port 22: Connection timed out",
    "unreachable": true
}

$ ping server01
PING server01: 56 bytes, 0 received, 100% packet loss   ← host down

$ # After host comes back:
$ ansible all -m ping
server01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

---

## Section 13: Database Errors — Sample Outputs

### #121 MySQL Too Many Connections

**Error seen:**
```
$ mysql -u root -p
ERROR 1040 (HY000): Too many connections

$ mysql -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"
ERROR 1040 (HY000): Too many connections   ← even root can't connect!
```

**Diagnosis & Fix:**
```
# Connect via socket (bypasses connection limit for root):
$ mysql -u root -p --socket=/var/run/mysqld/mysqld.sock

mysql> SHOW VARIABLES LIKE 'max_connections';
+-----------------+-------+
| Variable_name   | Value |
+-----------------+-------+
| max_connections | 100   |   ← too low!
+-----------------+-------+

mysql> SHOW STATUS LIKE 'Threads_connected';
+-------------------+-------+
| Variable_name     | Value |
+-------------------+-------+
| Threads_connected | 100   |   ← at max!
+-------------------+-------+

mysql> SET GLOBAL max_connections = 500;
Query OK, 0 rows affected

mysql> SHOW PROCESSLIST;
+----+------+-----------+------+---------+------+-------+
| Id | User | Host      | db   | Command | Time | State |
+----+------+-----------+------+---------+------+-------+
| 1  | app  | 10.0.0.5  | prod | Sleep   | 3600 | NULL  |  ← idle 1 hour!
| 2  | app  | 10.0.0.5  | prod | Sleep   | 3598 | NULL  |  ← idle connections
...
mysql> KILL 1;   # Kill idle connections
```

---

### #122–#130 (Database condensed)

**#122 PostgreSQL role not found:**
```
$ psql -U myapp -d mydb
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed:
FATAL:  role "myapp" does not exist

$ sudo -u postgres psql
postgres=# \du
                                   List of roles
 Role name |         Attributes
-----------+-----------------------------------------------------
 postgres  | Superuser, Create role, Create DB, Replication

postgres=# CREATE ROLE myapp WITH LOGIN PASSWORD 'secret';
CREATE ROLE
postgres=# GRANT ALL PRIVILEGES ON DATABASE mydb TO myapp;
GRANT
postgres=# \q

$ psql -U myapp -d mydb   ← now works
mydb=>
```

**#123 Redis NOAUTH:**
```
$ redis-cli ping
NOAUTH Authentication required

$ redis-cli -a mypassword ping
Warning: Using a password with '-a' or '-u' option on the command line interface may not be safe.
PONG   ← authenticated!

$ redis-cli
127.0.0.1:6379> AUTH mypassword
OK
127.0.0.1:6379> PING
PONG
```

**#126 Elasticsearch master not discovered:**
```
$ curl -s localhost:9200/_cluster/health?pretty
{
  "cluster_name" : "my-cluster",
  "status" : "red",                              ← cluster is RED
  "timed_out" : true,
  "number_of_nodes" : 1,
  "number_of_data_nodes" : 1,
  "unassigned_shards" : 15
}

$ curl -s localhost:9200/_cat/nodes?v
ip            heap.percent ram.percent cpu node.role node.name
10.0.0.51           45          78     2  m         node-1    ← only 1 of 3 nodes online

# Fix: bring other nodes back online, then:
$ curl -s localhost:9200/_cluster/health?pretty | grep status
  "status" : "green"   ← recovered!
```

---

## Section 14: CI/CD & Automation — Sample Outputs

### #131–#140 (Condensed)

**#133 Terraform state lock:**
```
$ terraform apply
╷
│ Error: Error acquiring the state lock
│
│ Error message: ConditionalCheckFailedException: The conditional request failed
│ Lock Info:
│   ID:        abc123-def4-5678-90ab
│   Path:      s3://my-bucket/terraform.tfstate
│   Operation: OperationTypeApply
│   Who:       john@server
│   Created:   2024-01-15 09:30:00.000 UTC
│   Info:      Previous apply crashed at 09:35
╵

$ terraform force-unlock abc123-def4-5678-90ab
Do you really want to force-unlock?
  Lock Info:
    ID: abc123-def4-5678-90ab
  Enter a value: yes
Terraform state has been successfully unlocked!
```

**#135 Helm chart not found:**
```
$ helm install myapp stable/myapp
Error: repo stable not found

$ helm repo list
NAME    URL
bitnami https://charts.bitnami.com/bitnami

$ helm repo add stable https://charts.helm.sh/stable
"stable" has been added to your repositories

$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "stable" chart repository

$ helm search repo myapp
NAME              CHART VERSION   APP VERSION
stable/myapp      1.2.3           2.0.0

$ helm install myapp stable/myapp   ← now works
```

**#136 kubectl Forbidden:**
```
$ kubectl get pods -n production
Error from server (Forbidden): pods is forbidden:
User "john" cannot list resource "pods" in API group ""
in the namespace "production"

$ kubectl auth can-i list pods -n production --as=john
no

$ kubectl create rolebinding john-viewer \
    --clusterrole=view \
    --user=john \
    --namespace=production
rolebinding.rbac.authorization.k8s.io/john-viewer created

$ kubectl auth can-i list pods -n production --as=john
yes

$ kubectl get pods -n production   ← now works
NAME                    READY   STATUS    RESTARTS
webapp-7d9f-xk2p9      1/1     Running   0
```

**#140 ArgoCD out of sync:**
```
$ argocd app get myapp
Name:               myapp
Project:            default
Server:             https://kubernetes.default.svc
Repo:               https://github.com/myorg/myapp
Target:             main
Path:               k8s/
SyncStatus:         OutOfSync    ← not in sync!
HealthStatus:       Healthy

$ argocd app diff myapp
===== apps/Deployment myapp/myapp ======
8,8c8,8
<     replicas: 2        ← Git says 2
---
>     replicas: 5        ← cluster has 5 (manually scaled!)

$ argocd app sync myapp
TIMESTAMP   GROUP  KIND        NAMESPACE  NAME    STATUS   HEALTH
10:30:01    apps   Deployment  myapp      myapp   Synced   Healthy

$ argocd app get myapp | grep SyncStatus
SyncStatus:  Synced   ← back in sync!
```

---

## Section 15: Performance & Observability — Sample Outputs

### #141 perf Permission Denied

**Error seen:**
```
$ perf stat ls
Error:
You may not have permission to collect stats.

Consider adjusting /proc/sys/kernel/perf_event_paranoid:
  -1 - Not paranoid at all
   0 - Disallow raw tracepoint access for unpriv
   1 - Disallow cpu events for unpriv
   2 - Disallow kernel profiling for unpriv

$ cat /proc/sys/kernel/perf_event_paranoid
4    ← very restrictive
```

**Fix output:**
```
$ sysctl -w kernel.perf_event_paranoid=1
kernel.perf_event_paranoid = 1

$ perf stat ls
Performance counter stats for 'ls':

         0.824857      task-clock (msec)         #    0.789 CPUs utilized
                1      context-switches          #    1.213 K/sec
                0      cpu-migrations            #    0.000 K/sec
              234      page-faults               #    0.284 M/sec
        2,456,789      cycles                    #    2.979 GHz
        1,234,567      instructions              #    0.50  insn per cycle

       0.001045022 seconds time elapsed   ← working!
```

---

### #142–#150 (Condensed)

**#142 strace permission denied:**
```
$ strace -p 1234
strace: attach: ptrace(PTRACE_SEIZE, 1234): Operation not permitted

$ cat /proc/sys/kernel/yama/ptrace_scope
1    ← only parent processes can trace

$ sudo strace -p 1234
strace: Process 1234 attached
read(5, "", 4096)                       = 0
epoll_wait(4, [{EPOLLIN, {u32=5, u64=5}}], 128, -1) = 1   ← tracing works!
```

**#143 Prometheus many-to-many:**
```
$ # Query fails:
{job="api"} * {job="api"}
Error: many-to-many matching not allowed: matching labels must be unique on one side

$ # Fixed with group_left:
rate(http_requests_total[5m]) * on(job, instance) group_left(version) build_info
```

**#144 Grafana no data source:**
```
# Grafana dashboard shows: "No data source found"

$ curl -s http://localhost:9090/api/v1/query?query=up
{"status":"success","data":{"resultType":"vector","result":[...]}}
# Prometheus is up — Grafana config is wrong

# Grafana UI → Configuration → Data Sources → Add Prometheus
# URL: http://prometheus:9090 (use service name, not localhost)
# Click "Save & Test"
# ✓ Data source is working   ← fixed!
```

**#147 sar cannot open file:**
```
$ sar -u 1 3
Cannot open /var/log/sa/sa15: No such file or directory

$ systemctl status sysstat
● sysstat.service - Resets System Activity Logs
     Active: inactive (dead)   ← sysstat not running!

$ systemctl enable --now sysstat
$ /usr/lib/sysstat/sa1 1 1     # Force first data collection

$ sar -u 1 3
Linux 6.5.0-15-generic (server)  01/15/2024  _x86_64_  (4 CPU)

10:30:01        CPU     %user   %system   %iowait   %idle
10:30:02        all      2.51      0.75      0.00     96.74
10:30:03        all      1.25      0.50      0.25     98.00
10:30:04        all      3.00      1.00      0.00     96.00
```

**#149 iostat device not found:**
```
$ iostat /dev/nvme0n1
/dev/nvme0n1: No such file or directory

$ cat /proc/diskstats | grep nvme
 259       0 nvme0n1 ...    ← device IS in diskstats

$ iostat -d -x 1 3     # Use without device filter
Device      r/s   w/s  rMB/s  wMB/s  %util
nvme0n1    45.2  23.1   12.3    4.5   8.2   ← shows up correctly!
```

**#150 systemd-analyze permission denied:**
```
$ systemd-analyze
Failed to connect to bus: No such file or directory

$ sudo systemd-analyze
Startup finished in 2.345s (firmware) + 1.234s (loader) + 3.456s (kernel) + 8.901s (userspace) = 15.936s
graphical.target reached after 8.876s in userspace

$ sudo systemd-analyze blame | head -10
8.234s apt-daily.service
4.567s NetworkManager-wait-online.service
2.345s plymouth-quit-wait.service
1.234s dev-sda1.device
0.987s accounts-daemon.service
0.876s udisks2.service
0.765s ModemManager.service
0.654s polkit.service
0.543s rsyslog.service
0.432s ssh.service

$ sudo systemd-analyze critical-chain
The time when unit became active or started is printed after the "@" character.
The time the unit took to start is printed after the "+" character.

graphical.target @8.876s
└─multi-user.target @8.875s
  └─NetworkManager-wait-online.service @4.308s +4.567s   ← biggest bottleneck!
    └─NetworkManager.service @1.234s +3.074s
      └─network.target @1.233s
```

---

*DevOps Shack — Linux Troubleshooting Guide 2026 Edition*
