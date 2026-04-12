# Kubernetes Issues — Sample Outputs & Diagnosis Guide

> **How to read this file:**
> - `# ← ⚠️ PROBLEM` — this value/line is the root cause
> - `# ← ✅ EXPECTED` — this is what a healthy value looks like
> - `# ← 🔍 CHECK THIS` — important value to compare
> Each issue shows: **Broken output → What to look for → Healthy output**

---

# Category 1 — Pod Failures

---

## Issue 1 — CrashLoopBackOff

### Step 1 — `kubectl get pods`

```
NAMESPACE   NAME                              READY   STATUS              RESTARTS        AGE
default     my-app-7d6f9b4c8-xk2pq           0/1     CrashLoopBackOff    6 (2m ago)      15m
                                              ^^^     ^^^^^^^^^^^^^^^^    ^               
                                              # ← ⚠️ PROBLEM: 0/1 = not ready
                                              #        CrashLoopBackOff = crashing repeatedly
                                              #        RESTARTS=6 = crashed 6 times already
```

### Step 2 — `kubectl describe pod my-app-7d6f9b4c8-xk2pq`

```
Name:         my-app-7d6f9b4c8-xk2pq
Namespace:    default
Status:       Running

Containers:
  my-app:
    State:          Waiting
      Reason:       CrashLoopBackOff        # ← ⚠️ PROBLEM: currently waiting to restart
    Last State:     Terminated
      Reason:       Error                   # ← ⚠️ PROBLEM: it crashed
      Exit Code:    1                       # ← ⚠️ PROBLEM: exit code 1 = app error
      Started:      Sun, 12 Apr 2026 10:00:00
      Finished:     Sun, 12 Apr 2026 10:00:10  # ← ⚠️ PROBLEM: ran for only 10 seconds
    Ready:          False                   # ← ⚠️ PROBLEM: pod not serving traffic
    Restart Count:  6                       # ← ⚠️ PROBLEM: crashed 6 times

Events:
  Warning  BackOff   2m    kubelet  Back-off restarting failed container  # ← ⚠️ PROBLEM
```

> **What Exit Code tells you:**
> - `Exit Code: 1`   → App crashed (missing config, DB not reachable, code bug)
> - `Exit Code: 137` → OOMKilled (app used too much memory)
> - `Exit Code: 139` → Segmentation fault (bug in native code)

### Step 3 — `kubectl logs my-app-7d6f9b4c8-xk2pq --previous`

```
2026-04-12 10:00:05 INFO  Starting application...
2026-04-12 10:00:06 INFO  Connecting to database...
2026-04-12 10:00:08 ERROR Failed to connect to DB: Connection refused  # ← ⚠️ PROBLEM
2026-04-12 10:00:08 ERROR Host: postgres-svc:5432 unreachable          # ← ⚠️ ROOT CAUSE
2026-04-12 10:00:08 FATAL Shutting down. Exit code 1
```

### Healthy Output (after fix)

```
NAMESPACE   NAME                              READY   STATUS    RESTARTS   AGE
default     my-app-7d6f9b4c8-xk2pq           1/1     Running   0          5m
                                              ^^^     ^^^^^^^   ^
                                              # ← ✅ 1/1 = container running
                                              # ← ✅ Running = healthy
                                              # ← ✅ RESTARTS=0 = stable
```

---

## Issue 2 — OOMKilled

### Step 1 — `kubectl get pods`

```
NAMESPACE   NAME                        READY   STATUS             RESTARTS       AGE
backend     flask-api-6d8b9f7c4-r2pml   0/1     OOMKilled          3 (5m ago)     20m
                                                 ^^^^^^^^^          ^
                                                 # ← ⚠️ PROBLEM: killed by kernel (out of memory)
                                                 # ← ⚠️ PROBLEM: 3 restarts = keeps happening
```

### Step 2 — `kubectl describe pod flask-api-6d8b9f7c4-r2pml`

```
Containers:
  flask-api:
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled               # ← ⚠️ PROBLEM: Out Of Memory killed
      Exit Code:    137                     # ← ⚠️ PROBLEM: 137 = OOM signal
      Started:      Sun, 12 Apr 2026 10:05:00
      Finished:     Sun, 12 Apr 2026 10:09:45

    Limits:
      memory:  256Mi                        # ← ⚠️ PROBLEM: limit is 256Mi (too low)
    Requests:
      memory:  128Mi
    
Events:
  Warning  OOMKilling  5m  kernel  Out of memory: Kill process 1234 (python3)
           Total vm: 512MB, anon-rss: 260MB, file-rss: 4MB  # ← ⚠️ PROBLEM: used 260MB > 256MB limit
```

### Step 3 — `kubectl top pod flask-api-6d8b9f7c4-r2pml`

```
NAME                        CPU     MEMORY
flask-api-6d8b9f7c4-r2pml   45m     251Mi    # ← ⚠️ PROBLEM: 251Mi of 256Mi limit used (98%)
                                     ^^^^^
                                     # Almost at limit — will be killed when it hits 256Mi
```

### Healthy Output (after fix — memory limit raised to 512Mi)

```
NAME                        CPU     MEMORY
flask-api-6d8b9f7c4-r2pml   45m     251Mi    # ← ✅ Same usage but limit is now 512Mi
                                              # ← ✅ 251Mi / 512Mi = 49% — safe headroom
```

---

## Issue 3 — ImagePullBackOff

### Step 1 — `kubectl get pods`

```
NAMESPACE   NAME                        READY   STATUS             RESTARTS   AGE
default     my-app-8b7d9c6f4-k9lmn      0/1     ImagePullBackOff   0          3m
                                                 ^^^^^^^^^^^^^^^^
                                                 # ← ⚠️ PROBLEM: cannot pull image from registry
```

### Step 2 — `kubectl describe pod my-app-8b7d9c6f4-k9lmn`

```
Containers:
  my-app:
    Image:          myrepo.example.com/myapp:v2.1.0    # ← 🔍 CHECK THIS image name
    Image ID:
    Ready:          False
    
Events:
  Warning  Failed     2m    kubelet  Failed to pull image
           "myrepo.example.com/myapp:v2.1.0":
           rpc error: code = Unknown
           desc = failed to pull and unpack image:
           unauthorized: authentication required         # ← ⚠️ PROBLEM: no registry credentials

  Warning  Failed     2m    kubelet  Error: ErrImagePull  # ← ⚠️ PROBLEM
  Warning  BackOff    90s   kubelet  Back-off pulling image  # ← ⚠️ PROBLEM: retrying
```

> **Other common error messages:**
> - `not found` → wrong image name or tag does not exist
> - `unauthorized` → missing or wrong image pull secret
> - `connection refused` → registry URL is wrong

### Healthy Output (after adding pull secret)

```
Events:
  Normal  Pulling    30s   kubelet  Pulling image "myrepo.example.com/myapp:v2.1.0"
  Normal  Pulled     15s   kubelet  Successfully pulled image in 15s   # ← ✅ SUCCESS
  Normal  Created    14s   kubelet  Created container my-app
  Normal  Started    14s   kubelet  Started container my-app            # ← ✅ RUNNING
```

---

## Issue 4 — Pod Stuck in Pending

### Step 1 — `kubectl get pods`

```
NAMESPACE   NAME                        READY   STATUS    RESTARTS   AGE
production  api-server-9c8d7f6b4-p3qrs  0/1     Pending   0          10m
                                                 ^^^^^^^
                                                 # ← ⚠️ PROBLEM: never scheduled to any node
                                                 # ← ⚠️ RESTARTS=0 means it never even started
```

### Step 2 — `kubectl describe pod api-server-9c8d7f6b4-p3qrs`

```
Node:           <none>      # ← ⚠️ PROBLEM: not assigned to any node

Conditions:
  PodScheduled:   False     # ← ⚠️ PROBLEM: scheduler couldn't place it

Events:
  Warning  FailedScheduling  30s  default-scheduler
           0/4 nodes are available:                    # ← ⚠️ PROBLEM: checked all 4 nodes
           2 Insufficient cpu,                         # ← ⚠️ PROBLEM: 2 nodes don't have enough CPU
           2 Insufficient memory.                      # ← ⚠️ PROBLEM: 2 nodes don't have enough RAM
           preemption: 0/4 nodes are available
```

### Step 3 — `kubectl describe nodes | grep -A5 "Allocated resources"`

```
Node: calico-prod-worker
  Allocated resources:
    Resource            Requests    Limits
    cpu                 1850m/2     950m/2      # ← ⚠️ PROBLEM: 1850m of 2000m used (92%)
    memory              1800Mi/2Gi  1200Mi/2Gi  # ← ⚠️ PROBLEM: 1800Mi of 2048Mi used (88%)
```

> **Pod was requesting:**
> ```
> requests:
>   cpu: "500m"     # ← ⚠️ No node has 500m free
>   memory: "512Mi" # ← ⚠️ No node has 512Mi free
> ```

### Healthy Output (after reducing requests)

```
Events:
  Normal  Scheduled  1s   default-scheduler  Successfully assigned production/api-server-xxx
                                             to calico-prod-worker2          # ← ✅ SCHEDULED
  Normal  Pulling    1s   kubelet            Pulling image...
  Normal  Started    10s  kubelet            Started container api-server     # ← ✅ RUNNING
```

---

## Issue 5 — Init Container Failing

### Step 1 — `kubectl get pods`

```
NAMESPACE   NAME                        READY   STATUS       RESTARTS   AGE
default     web-app-7f8c9d6b4-m4nop     0/1     Init:0/1     3          8m
                                                 ^^^^^^^^
                                                 # ← ⚠️ PROBLEM: stuck in init container
                                                 # ← ⚠️ 0 of 1 init containers completed
```

### Step 2 — `kubectl describe pod web-app-7f8c9d6b4-m4nop`

```
Init Containers:
  wait-for-db:                                # ← 🔍 CHECK THIS: name of init container
    State:      Terminated
      Reason:   Error                         # ← ⚠️ PROBLEM: init container crashed
      Exit Code: 1                            # ← ⚠️ PROBLEM
    
Main Containers:
  web-app:
    State:      Waiting
      Reason:   PodInitializing               # ← ⚠️ PROBLEM: blocked, waiting for init

Events:
  Warning  BackOff  3m  kubelet  Back-off restarting failed init container wait-for-db
```

### Step 3 — `kubectl logs web-app-7f8c9d6b4-m4nop -c wait-for-db`

```
Waiting for postgres-svc:5432...
Attempt 1/30: connecting to postgres-svc.default.svc.cluster.local:5432
nc: bad address 'postgres-svc.default.svc.cluster.local'   # ← ⚠️ PROBLEM: DNS not resolving
Attempt 2/30: ...
Attempt 30/30: giving up after 30 attempts                  # ← ⚠️ PROBLEM: DB never found
exit 1
```

### Healthy Output

```
Init Containers:
  wait-for-db:
    State:      Terminated
      Reason:   Completed        # ← ✅ Init container succeeded
      Exit Code: 0               # ← ✅ Exit 0 = success

Main Containers:
  web-app:
    State:      Running          # ← ✅ Main app now running
    Ready:      True
```

---

# Category 2 — Networking Issues

---

## Issue 6 — Service Not Reachable

### Step 1 — `kubectl get endpoints frontend-svc -n frontend`

```
NAME           ENDPOINTS         AGE
frontend-svc   <none>            5d    # ← ⚠️ PROBLEM: no pods backing this service
                ^^^^^^
                # This means: service selector doesn't match any pod labels
```

### Step 2 — `kubectl describe svc frontend-svc -n frontend`

```
Name:              frontend-svc
Namespace:         frontend
Selector:          app=frontend          # ← 🔍 CHECK THIS: service expects label app=frontend
Endpoints:         <none>                # ← ⚠️ PROBLEM: nothing matched
```

### Step 3 — `kubectl get pods -n frontend --show-labels`

```
NAME                         READY   STATUS    LABELS
frontend-6d9f7c8b4-xk2pl     1/1     Running   app=web-frontend,version=v2  # ← ⚠️ PROBLEM
                                                ^^^^^^^^^^^^^^^^
                                                # app=web-frontend (pod)
                                                # vs
                                                # app=frontend (service expects)
                                                # MISMATCH! That's why endpoints = <none>
```

### Healthy Output (after fixing label)

```
NAME           ENDPOINTS                         AGE
frontend-svc   10.244.1.5:80,10.244.2.3:80       5d    # ← ✅ 2 pod IPs listed = service works
```

---

## Issue 7 — DNS Resolution Failure

### `kubectl run dns-test --image=busybox --rm -it -- nslookup frontend-svc.frontend.svc.cluster.local`

```
# BROKEN — DNS not resolving:
Server:    10.96.0.10
Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local

nslookup: can't resolve 'frontend-svc.frontend.svc.cluster.local'  # ← ⚠️ PROBLEM

# ----- Common mistakes -----

# Wrong: short name from different namespace (no cross-namespace resolution)
curl http://frontend-svc/          # ← ⚠️ PROBLEM: only works in same namespace

# Wrong: missing namespace
curl http://frontend-svc.svc.cluster.local/   # ← ⚠️ PROBLEM: missing namespace segment

# Correct format:
curl http://frontend-svc.frontend.svc.cluster.local/   # ← ✅ full DNS name
#            ^service  ^namespace ^domain
```

### `kubectl get pods -n kube-system | grep coredns`

```
# BROKEN CoreDNS:
NAME                       READY   STATUS             RESTARTS   AGE
coredns-5d78c9869d-abc12   0/1     CrashLoopBackOff   8          1h   # ← ⚠️ PROBLEM

# HEALTHY CoreDNS:
NAME                       READY   STATUS    RESTARTS   AGE
coredns-5d78c9869d-abc12   1/1     Running   0          5d            # ← ✅ GOOD
coredns-5d78c9869d-def34   1/1     Running   0          5d            # ← ✅ GOOD
```

---

## Issue 8 — Ingress Not Routing (404 / 502)

### `kubectl get ingress -n frontend`

```
NAME              CLASS   HOSTS                    ADDRESS     PORTS   AGE
frontend-ingress  nginx   myapp.devopscab.com      <none>      80      5m
                                                   ^^^^^^
                                                   # ← ⚠️ PROBLEM: no ADDRESS assigned
                                                   # Ingress controller is not running
```

### `kubectl describe ingress frontend-ingress -n frontend`

```
Rules:
  Host                    Path  Backends
  ----                    ----  --------
  myapp.devopscab.com     /     frontend-svc:8080 (<error: endpoints "frontend-svc" not found>)
                                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                   # ← ⚠️ PROBLEM: service doesn't exist
                                                   # OR wrong port number
```

### Ingress Controller Logs — `kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx`

```
# 502 Bad Gateway cause:
W  upstream "http://10.244.1.5:8080" unreachable    # ← ⚠️ PROBLEM: pod not accepting connections
E  connect() failed (111: Connection refused)        # ← ⚠️ PROBLEM: wrong port or pod crashing

# 404 Not Found cause:
W  "GET /api/users HTTP/1.1" 404                     # ← ⚠️ PROBLEM: path doesn't match ingress rules
```

### Healthy Output

```
NAME              CLASS   HOSTS                    ADDRESS         PORTS
frontend-ingress  nginx   myapp.devopscab.com      192.168.1.100   80    # ← ✅ ADDRESS assigned

# Logs show:
I  "GET / HTTP/1.1" 200 1234 "http://myapp.devopscab.com" 0.005s         # ← ✅ 200 OK
```

---

## Issue 9 — Network Policy Blocking Traffic

### `kubectl exec backend-pod -- curl -v http://frontend-svc.frontend.svc.cluster.local`

```
* Trying 10.96.152.167:80...
* connect to 10.96.152.167 port 80 failed: Connection timed out   # ← ⚠️ PROBLEM
* Failed to connect to frontend-svc port 80 after 30000ms
curl: (28) Connection timed out after 30001 milliseconds           # ← ⚠️ PROBLEM

# Timeout (not refused) = NetworkPolicy is silently dropping packets
```

### `kubectl get networkpolicies -n frontend`

```
NAME                   POD-SELECTOR   AGE
deny-all               <none>         5d    # ← ⚠️ PROBLEM: deny-all policy exists
allow-from-same-ns     app=frontend   5d    # Only allows traffic from same namespace
                                            # backend namespace is BLOCKED
```

### Healthy Output (after adding allow rule)

```
* Trying 10.96.152.167:80...
* Connected to frontend-svc port 80                               # ← ✅ CONNECTED
< HTTP/1.1 200 OK                                                  # ← ✅ 200 response
```

---

## Issue 10 — LoadBalancer EXTERNAL-IP Pending

### `kubectl get svc -n default`

```
NAME         TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
my-app-svc   LoadBalancer   10.96.45.123   <pending>     80:31234/TCP   10m
                                           ^^^^^^^^^
                                           # ← ⚠️ PROBLEM: no external IP assigned
                                           # Expected on Kind/bare metal — no cloud LB available
```

### Fix — Use port-forward instead on Kind

```
kubectl port-forward svc/my-app-svc 8080:80 -n default
Forwarding from 127.0.0.1:8080 -> 80     # ← ✅ Access via localhost:8080
```

---

# Category 3 — Resource Issues

---

## Issue 11 — Node NotReady

### `kubectl get nodes`

```
NAME                        STATUS     ROLES           AGE   VERSION
calico-prod-control-plane   Ready      control-plane   72d   v1.35.0   # ← ✅ OK
calico-prod-worker          Ready      <none>          72d   v1.35.0   # ← ✅ OK
calico-prod-worker2         NotReady   <none>          72d   v1.35.0   # ← ⚠️ PROBLEM
calico-prod-worker3         Ready      <none>          72d   v1.35.0   # ← ✅ OK
```

### `kubectl describe node calico-prod-worker2`

```
Conditions:
  Type                Status   Reason
  ----                ------   ------
  MemoryPressure      False    KubeletHasSufficientMemory   # ← ✅ OK
  DiskPressure        True     KubeletHasDiskPressure       # ← ⚠️ PROBLEM: disk is full
  PIDPressure         False    KubeletHasSufficientPID      # ← ✅ OK
  Ready               False    KubeletNotReady              # ← ⚠️ PROBLEM: node offline

Events:
  Warning  EvictionThresholdMet  2m  kubelet
           Attempting to reclaim ephemeral-storage         # ← ⚠️ PROBLEM: disk eviction started
```

### Healthy Output

```
Conditions:
  MemoryPressure   False   KubeletHasSufficientMemory   # ← ✅
  DiskPressure     False   KubeletHasSufficientDisk     # ← ✅
  PIDPressure      False   KubeletHasSufficientPID      # ← ✅
  Ready            True    KubeletReady                 # ← ✅ ALL GREEN
```

---

## Issue 12 — Evicted Pods

### `kubectl get pods -A | grep Evicted`

```
NAMESPACE    NAME                          READY   STATUS    RESTARTS   AGE
default      api-server-7d6f9-abc12        0/1     Evicted   0          2h    # ← ⚠️ PROBLEM
backend      flask-api-8c7d4-def34         0/1     Evicted   0          2h    # ← ⚠️ PROBLEM
frontend     react-app-9b8e3-ghi56         0/1     Evicted   0          2h    # ← ⚠️ PROBLEM
```

### `kubectl describe pod api-server-7d6f9-abc12 -n default`

```
Status:   Failed
Reason:   Evicted                                      # ← ⚠️ PROBLEM
Message:  The node was low on resource: memory.
          Threshold quantity: 100Mi, available: 45Mi.  # ← ⚠️ PROBLEM: node had only 45Mi left
          Container api-server was using 890Mi.        # ← ⚠️ ROOT CAUSE: no limits set
```

---

## Issue 13 — CPU Throttling (Silent Performance Issue)

### `kubectl top pods -n backend`

```
NAME                        CPU     MEMORY
flask-api-6d8b9f7c4-r2pml   499m    180Mi   # ← ⚠️ PROBLEM: 499m of 500m limit (99%)
                             ^^^^
                             # CPU is pinned at the limit — app is being throttled
                             # Response time will be high — NO errors, NO crashes
                             # This is why: "app is slow but no alerts firing"
```

### In New Relic — APM Signature of CPU Throttling

```
Transactions:
  /api/orders    avg duration: 2.8s   error rate: 0%   # ← ⚠️ PROBLEM: slow but no errors
  /api/health    avg duration: 2.1s   error rate: 0%   # ← ⚠️ PROBLEM: even health check is slow

# CPU throttling signature = HIGH latency + ZERO errors
# If it were a code bug you'd see errors too
```

### Healthy Output (after raising CPU limit)

```
NAME                        CPU     MEMORY
flask-api-6d8b9f7c4-r2pml   220m    180Mi   # ← ✅ 220m of 1000m limit (22%) — headroom available

# APM:
/api/orders    avg duration: 0.2s   error rate: 0%   # ← ✅ FAST
```

---

## Issue 14 — No Resource Limits Set

### `kubectl describe pod runaway-app-xxx -n default`

```
Containers:
  runaway-app:
    Limits:       <none>      # ← ⚠️ PROBLEM: no limits — can use ALL node resources
    Requests:     <none>      # ← ⚠️ PROBLEM: no requests — scheduler has no guidance
```

### `kubectl top pods -n default`

```
NAME                   CPU      MEMORY
runaway-app-xxx        3800m    7.8Gi   # ← ⚠️ PROBLEM: consuming almost entire node
other-app-yyy          10m      50Mi    # ← ⚠️ PROBLEM: starved by runaway app
another-app-zzz        5m       30Mi    # ← ⚠️ PROBLEM: starved
```

---

## Issue 15 — HPA Not Scaling

### `kubectl get hpa -n production`

```
NAME      REFERENCE            TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
app-hpa   Deployment/my-app    <unknown>/70%   2         10        2          5m
                               ^^^^^^^^^
                               # ← ⚠️ PROBLEM: <unknown> means metrics server can't get CPU data
                               # HPA cannot make scaling decisions
                               # Replicas stuck at 2 even under heavy load
```

### `kubectl describe hpa app-hpa -n production`

```
Events:
  Warning  FailedGetScale  2m  horizontal-pod-autoscaler
           failed to get cpu utilization:
           unable to get metrics for resource cpu:
           unable to fetch metrics from resource metrics API:
           the server is currently unable to handle the request   # ← ⚠️ PROBLEM: metrics server down
```

### `kubectl get pods -n kube-system | grep metrics`

```
NAME                               READY   STATUS             RESTARTS   AGE
metrics-server-7d9d5c8b4-abc12     0/1     CrashLoopBackOff   5          10m  # ← ⚠️ PROBLEM
```

### Healthy Output (after fixing metrics server)

```
NAME      REFERENCE            TARGETS    MINPODS   MAXPODS   REPLICAS
app-hpa   Deployment/my-app    85%/70%    2         10        6          # ← ✅ Scaled to 6!
                               ^^^^^^^
                               # 85% CPU usage > 70% threshold
                               # HPA added replicas to bring it down
```

---

# Category 4 — Configuration Errors

---

## Issue 16 — Missing Secret / ConfigMap

### `kubectl get pods -n backend`

```
NAME                        READY   STATUS                       RESTARTS   AGE
api-server-7d6f9b4c8-p3q    0/1     CreateContainerConfigError   0          2m
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    # ← ⚠️ PROBLEM: container config is wrong
                                    # Usually missing Secret or ConfigMap
```

### `kubectl describe pod api-server-7d6f9b4c8-p3q -n backend`

```
Events:
  Warning  Failed  30s  kubelet  Error: secret "db-credentials" not found   # ← ⚠️ PROBLEM
                                        ^^^^^^^^^^^^^^^^^^^^^^^^
                                        # Secret "db-credentials" is referenced in deployment
                                        # but was never created in this namespace
```

### `kubectl get secrets -n backend`

```
NAME                   TYPE     DATA   AGE
default-token-xyz      Opaque   3      72d
# db-credentials is NOT listed   ← ⚠️ PROBLEM: the required secret is missing
```

### Healthy Output (after creating secret)

```
kubectl get secrets -n backend
NAME                   TYPE     DATA   AGE
db-credentials         Opaque   2      5s    # ← ✅ Secret now exists
default-token-xyz      Opaque   3      72d

kubectl get pods -n backend
NAME                        READY   STATUS    RESTARTS   AGE
api-server-7d6f9b4c8-p3q    1/1     Running   0          30s   # ← ✅ Now running
```

---

## Issue 17 — Wrong Environment Variable

### `kubectl exec api-server-xxx -n backend -- env | grep DB`

```
DB_HOST=localhost          # ← ⚠️ PROBLEM: pointing to localhost (no DB there)
DB_PORT=5432
DB_NAME=mydb
DB_PASSWORD=secret123
```

### App logs showing the result

```
2026-04-12 ERROR  Connection refused: localhost:5432   # ← ⚠️ PROBLEM: connecting to wrong host
2026-04-12 ERROR  FATAL: database "mydb" not found
```

### Healthy Output (after fix)

```
DB_HOST=postgres-svc.database.svc.cluster.local   # ← ✅ Correct Kubernetes DNS name
DB_PORT=5432
DB_NAME=mydb
DB_PASSWORD=secret123

# App logs:
2026-04-12 INFO  Connected to postgres-svc.database.svc.cluster.local:5432   # ← ✅
2026-04-12 INFO  Database connection pool initialized (5 connections)
```

---

## Issue 18 — Liveness Probe Failing (Pod restarts every few min)

### `kubectl describe pod my-app-xxx -n default`

```
Containers:
  my-app:
    Liveness:   http-get http://:8080/healthz delay=5s timeout=1s period=10s
                                 ^^^^^^^^
                                 # ← ⚠️ PROBLEM: probe hits /healthz
                                 # But the actual endpoint is /health (no 'z')

    State:          Running
    Restart Count:  12           # ← ⚠️ PROBLEM: 12 restarts from liveness failures

Events:
  Warning  Unhealthy  30s  kubelet  Liveness probe failed:
           HTTP probe failed with statuscode: 404       # ← ⚠️ PROBLEM: /healthz returns 404
  Warning  Killing    30s  kubelet  Container my-app failed liveness probe,
           will be restarted                            # ← ⚠️ PROBLEM: killed and restarted
```

### Healthy Output (after fixing probe path)

```
Liveness:   http-get http://:8080/health delay=30s timeout=1s period=10s
                              ^^^^^^^
                              # ← ✅ Correct path

Events:
  Normal  Started  5m  kubelet  Started container my-app   # ← ✅ No probe failures
  # No Warning events = probes passing
```

---

## Issue 19 — Readiness Probe Failing (Pod never gets traffic)

### `kubectl get pods -n backend`

```
NAME                        READY   STATUS    RESTARTS   AGE
api-server-7d6f9b4c8-p3q    0/1     Running   0          5m
                             ^^^
                             # ← ⚠️ PROBLEM: 0/1 = pod is Running but NOT READY
                             # Traffic will NOT be sent to this pod
                             # Service endpoints will show <none>
```

### `kubectl describe pod api-server-7d6f9b4c8-p3q -n backend`

```
Readiness:  http-get http://:8080/ready delay=5s timeout=1s period=5s
            
Events:
  Warning  Unhealthy  4m  kubelet  Readiness probe failed:
           Get "http://10.244.1.5:8080/ready": dial tcp 10.244.1.5:8080:
           connect: connection refused                   # ← ⚠️ PROBLEM: app not listening yet
           
# Why: initialDelaySeconds=5 but app takes 30s to start
# Probe fires at 5s — app not ready yet — marked not ready — traffic blocked
```

### Healthy Output (after fixing initialDelaySeconds)

```
NAME                        READY   STATUS    RESTARTS   AGE
api-server-7d6f9b4c8-p3q    1/1     Running   0          2m   # ← ✅ 1/1 = Ready and serving traffic

kubectl get endpoints api-server-svc -n backend
NAME             ENDPOINTS
api-server-svc   10.244.1.5:8080    # ← ✅ Pod IP listed = traffic flowing
```

---

## Issue 20 — Wrong Image Tag `:latest`

### `kubectl describe pod my-app-worker-xxx -n default`

```
Containers:
  worker-1:
    Image: myrepo/myapp:latest    # ← ⚠️ PROBLEM on calico-prod-worker (cached old image)
    Image ID: sha256:abc123...

  worker-2:
    Image: myrepo/myapp:latest    # ← ⚠️ PROBLEM on calico-prod-worker2 (pulled new image)
    Image ID: sha256:def456...    # ← ⚠️ DIFFERENT SHA — different code running!
                   ^^^^^^^
                   # Two pods with same :latest tag but different actual code
                   # This causes inconsistent behavior — some requests work, some fail
```

---

# Category 5 — Storage Issues

---

## Issue 21 — PVC Stuck in Pending

### `kubectl get pvc -n database`

```
NAME        STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   AGE
postgres-pvc  Pending                                    fast-ssd       10m
               ^^^^^^^
               # ← ⚠️ PROBLEM: Pending for 10 minutes — should bind in seconds
               # StorageClass "fast-ssd" doesn't exist
```

### `kubectl describe pvc postgres-pvc -n database`

```
Events:
  Warning  ProvisioningFailed  9m  persistentvolume-controller
           storageclass.storage.k8s.io "fast-ssd" not found   # ← ⚠️ ROOT CAUSE
```

### `kubectl get storageclass`

```
NAME                 PROVISIONER              AGE
standard (default)   rancher.io/local-path    72d   # ← ✅ This exists
# "fast-ssd" is NOT listed                          # ← ⚠️ PROBLEM: wrong StorageClass in PVC
```

### Healthy Output (after fixing StorageClass)

```
NAME           STATUS   VOLUME          CAPACITY   STORAGECLASS   AGE
postgres-pvc   Bound    pvc-abc-xyz     10Gi       standard       5s   # ← ✅ BOUND
               ^^^^^
               # STATUS = Bound = volume allocated and ready
```

---

## Issue 22 — PV Not Released

### `kubectl get pv`

```
NAME         CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS     CLAIM                    AGE
pv-data-01   10Gi       RWO            Retain           Released   database/postgres-pvc    5d
                                       ^^^^^^           ^^^^^^^^
                                       # ← ⚠️ PROBLEM: Retain policy = manual cleanup needed
                                       # ← ⚠️ STATUS: Released = old claim deleted but PV not reusable
                                       # New PVC cannot bind to this PV
```

### Healthy Output (after clearing claimRef)

```
NAME         CAPACITY   STATUS      CLAIM   AGE
pv-data-01   10Gi       Available           5d   # ← ✅ Available = ready for new PVC
```

---

## Issue 23 — Disk Full on Node

### `kubectl describe node calico-prod-worker2`

```
Conditions:
  DiskPressure   True   KubeletHasDiskPressure   # ← ⚠️ PROBLEM: disk is full

Allocated resources:
  ephemeral-storage   95%                        # ← ⚠️ PROBLEM: 95% disk used
```

### Inside the node (via kubectl debug)

```
$ df -h
Filesystem      Size   Used  Avail  Use%  Mounted on
/dev/sda1        50G    48G   2G    96%   /           # ← ⚠️ PROBLEM: 96% full

$ du -sh /var/log/containers/* | sort -rh | head -5
8.5G  /var/log/containers/argocd-server-xxx.log       # ← ⚠️ PROBLEM: huge log file
3.2G  /var/log/containers/backend-xxx.log             # ← ⚠️ PROBLEM: no log rotation
```

---

# Category 6 — Deployment & Rollout

---

## Issue 24 — Deployment Stuck (Rollout Not Completing)

### `kubectl rollout status deployment/my-app -n production`

```
Waiting for deployment "my-app" rollout to finish:
1 out of 2 new replicas have been updated...   # ← ⚠️ PROBLEM: stuck for 10+ minutes
```

### `kubectl get pods -n production`

```
NAME                        READY   STATUS             RESTARTS   AGE
my-app-OLD-7d6f9-abc12      1/1     Running            0          2d    # ← old version still running
my-app-NEW-8e7g0-def34      0/1     CrashLoopBackOff   5          5m    # ← ⚠️ PROBLEM: new version crashing
                                    ^^^^^^^^^^^^^^^^
                                    # New pod keeps crashing — rollout is blocked
                                    # Old pod stays up (minAvailable=1 is satisfied)
                                    # Rollout will NEVER complete until new pod is healthy
```

---

## Issue 25 — Need to Rollback

### `kubectl rollout history deployment/my-app -n production`

```
REVISION  CHANGE-CAUSE
1         Initial deployment — v1.0.0     # ← ✅ working version
2         Upgrade to v1.1.0               # ← ✅ working version
3         Upgrade to v2.0.0               # ← ⚠️ PROBLEM: this version is broken
          ^
          # Currently on revision 3 — need to go back to revision 2
```

### Rollback command and result

```
kubectl rollout undo deployment/my-app -n production --to-revision=2

deployment.apps/my-app rolled back   # ← ✅ Rollback initiated

kubectl rollout status deployment/my-app -n production
deployment "my-app" successfully rolled out   # ← ✅ Back to v1.1.0
```

---

# Category 7 — Observability Issues

---

## Issue 27 — No Logs in New Relic

### `kubectl get pods -n newrelic | grep logging`

```
NAME                               READY   STATUS             RESTARTS   AGE
nri-bundle-newrelic-logging-abc    0/1     CrashLoopBackOff   8          1h   # ← ⚠️ PROBLEM
```

### `kubectl logs nri-bundle-newrelic-logging-abc -n newrelic`

```
[error] [output:http:http.0] http_api: could not send data to newrelic
[error] HTTP status: 403 Forbidden                  # ← ⚠️ PROBLEM: wrong license key
[error] License key rejected by New Relic API       # ← ⚠️ ROOT CAUSE
```

### Healthy Output

```
NAME                               READY   STATUS    RESTARTS   AGE
nri-bundle-newrelic-logging-abc    1/1     Running   0          5m   # ← ✅

# Logs show:
[info]  [output:http] Flushing chunk with 250 records to New Relic   # ← ✅ sending logs
[info]  HTTP status: 202                                              # ← ✅ accepted
```

---

## Issue 28 — Metrics Missing in New Relic

### New Relic NRQL Query Result

```
SELECT average(cpuUsedCores) FROM K8sContainerSample 
WHERE clusterName = 'kind-calico-prod' SINCE 30 minutes ago

Result: No data found   # ← ⚠️ PROBLEM: infrastructure agent not sending metrics
```

### `kubectl logs -n newrelic -l app.kubernetes.io/component=kubelet --tail=20`

```
time="2026-04-12" level=error msg="metric sender can't process"
error="IngestError: events were not accepted: 401 401 {}"   # ← ⚠️ PROBLEM: 401 = wrong key
```

### Healthy Logs

```
time="2026-04-12" level=info msg="Sending metrics to New Relic"
time="2026-04-12" level=info msg="202 Accepted"             # ← ✅ metrics accepted
```

---

## Issue 30 — RBAC Permission Denied

### Pod logs showing the error

```
2026-04-12 ERROR  k8s_client: failed to list pods
                  User "system:serviceaccount:monitoring:my-agent"   # ← ⚠️ PROBLEM
                  cannot list resource "pods"                         # ← ⚠️ PROBLEM
                  in API group "" at the cluster scope                # ← ⚠️ PROBLEM
                  Status: 403 Forbidden
```

### `kubectl get clusterrolebindings | grep my-agent`

```
# No output — no ClusterRoleBinding exists for this ServiceAccount   # ← ⚠️ PROBLEM
```

### Healthy Output (after adding RBAC)

```
kubectl get clusterrolebindings | grep my-agent
my-agent-reader   ClusterRole/pod-reader   1d    # ← ✅ binding exists

# Pod logs now show:
2026-04-12 INFO  Successfully listed 45 pods across 8 namespaces    # ← ✅ access granted
```

---

## Summary — Problem Indicators at a Glance

| What you see | What it means | First command to run |
|---|---|---|
| `CrashLoopBackOff` | App crashing repeatedly | `kubectl logs <pod> --previous` |
| `OOMKilled` | Memory limit exceeded | `kubectl top pod` + `describe` |
| `ImagePullBackOff` | Can't pull image | `kubectl describe pod` → check Events |
| `Pending` (long time) | No node can schedule it | `kubectl describe pod` → check Events |
| `Init:0/1` | Init container failed | `kubectl logs <pod> -c <init-container>` |
| `0/1 Running` | Running but not ready | `kubectl describe pod` → check Readiness probe |
| `Evicted` | Node ran out of resources | `kubectl describe pod` → check Message |
| `<unknown>` in HPA | Metrics server down | `kubectl top pods` → test if it works |
| `<none>` in Endpoints | Label mismatch | `kubectl describe svc` vs `kubectl get pods --show-labels` |
| `<pending>` in LoadBalancer | No cloud LB | Use NodePort or port-forward instead |

---

*Last updated: April 2026 | Cluster: kind-calico-prod | Reference: K8s_issues.md*
