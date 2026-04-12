# Kubernetes Issues — Real Output Samples

> **How to read this file:**
> Each issue shows you exactly what you will see on your terminal,
> with clear markers pointing to the problem and what healthy looks like.
>
> `# ⚠️ PROBLEM →` points to the broken value
> `# ✅ HEALTHY →` shows what it should look like when fixed
> `# 💡 MEANS →`  explains what that value means in plain English

---

# Issue 1 — CrashLoopBackOff

## What You See (Broken)

```bash
$ kubectl get pods -n default
```
```
NAME                   READY   STATUS              RESTARTS   AGE
my-app-7d6f9-xk2pq     0/1     CrashLoopBackOff    6          15m
                        ↑↑↑     ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑  ↑
                        # ⚠️ PROBLEM → 0 out of 1 container is working
                        # ⚠️ PROBLEM → pod keeps crashing and restarting
                        # ⚠️ PROBLEM → already crashed 6 times in 15 minutes
```

## Dig Deeper

```bash
$ kubectl describe pod my-app-7d6f9-xk2pq -n default
```
```
Containers:
  my-app:
    State:       Waiting
      Reason:    CrashLoopBackOff      # ⚠️ PROBLEM → currently paused before next restart

    Last State:  Terminated
      Reason:    Error                 # ⚠️ PROBLEM → it crashed (not graceful shutdown)
      Exit Code: 1                     # ⚠️ PROBLEM → 1 = app error (bad config, DB down, code bug)
      Started:   12 Apr 2026 10:00:00
      Finished:  12 Apr 2026 10:00:10  # ⚠️ PROBLEM → ran for only 10 seconds before dying

    Ready:          False              # ⚠️ PROBLEM → no traffic going to this pod
    Restart Count:  6                  # ⚠️ PROBLEM → happened 6 times already
```

## Read the Crash Log

```bash
$ kubectl logs my-app-7d6f9-xk2pq -n default --previous
```
```
2026-04-12 10:00:05  INFO   Starting application...
2026-04-12 10:00:06  INFO   Connecting to database at postgres-svc:5432
2026-04-12 10:00:09  ERROR  Connection refused: postgres-svc:5432   # ⚠️ PROBLEM → DB not reachable
2026-04-12 10:00:09  FATAL  Cannot start without database. Exiting.  # ⚠️ PROBLEM → app gives up
```

> 💡 **--previous** is important — without it you see logs from the current (waiting) state, not the crashed one

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n default
```
```
NAME                   READY   STATUS    RESTARTS   AGE
my-app-7d6f9-xk2pq     1/1     Running   0          5m
                        ↑↑↑     ↑↑↑↑↑↑↑  ↑
                        # ✅ HEALTHY → 1 out of 1 container running
                        # ✅ HEALTHY → Running = stable
                        # ✅ HEALTHY → 0 restarts = no crashes
```

---

# Issue 2 — OOMKilled (Out Of Memory)

## What You See (Broken)

```bash
$ kubectl get pods -n backend
```
```
NAME                READY   STATUS      RESTARTS   AGE
flask-api-6d8b-xxx  0/1     OOMKilled   3          20m
                             ↑↑↑↑↑↑↑↑↑
                             # ⚠️ PROBLEM → Kubernetes killed this pod because it used too much memory
                             # 💡 MEANS  → App needs more memory than the limit allows
```

## Dig Deeper

```bash
$ kubectl describe pod flask-api-6d8b-xxx -n backend
```
```
    Last State:  Terminated
      Reason:    OOMKilled        # ⚠️ PROBLEM → killed by the operating system, not by the app
      Exit Code: 137              # ⚠️ PROBLEM → 137 always means OOM kill

    Limits:
      memory:  256Mi              # ⚠️ PROBLEM → app is only allowed 256MB of RAM

Events:
  Warning  OOMKilling  5m  kernel
           Out of memory: Kill process 1234 (python3)
           Total vm: 512MB, anon-rss: 260MB   # ⚠️ PROBLEM → used 260MB, limit was 256MB
```

## Check Current Memory Usage

```bash
$ kubectl top pod flask-api-6d8b-xxx -n backend
```
```
NAME                CPU     MEMORY
flask-api-6d8b-xxx  45m     251Mi     # ⚠️ PROBLEM → 251MB used out of 256MB limit = 98% full
                             ↑↑↑↑↑
                             # Any small spike will kill this pod
```

## What It Looks Like When Fixed

```bash
$ kubectl top pod flask-api-6d8b-xxx -n backend
```
```
NAME                CPU     MEMORY
flask-api-6d8b-xxx  45m     251Mi     # ✅ HEALTHY → same usage (251MB) but limit is now 512MB
                                      # ✅ HEALTHY → 251/512 = 49% used, plenty of headroom
```

---

# Issue 3 — ImagePullBackOff

## What You See (Broken)

```bash
$ kubectl get pods -n default
```
```
NAME              READY   STATUS             RESTARTS   AGE
my-app-8b7d-xxx   0/1     ImagePullBackOff   0          3m
                           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                           # ⚠️ PROBLEM → Kubernetes cannot download the app's Docker image
                           # ⚠️ PROBLEM → pod never started even once (RESTARTS: 0)
```

## Dig Deeper

```bash
$ kubectl describe pod my-app-8b7d-xxx -n default
```
```
  Image: myrepo.example.com/myapp:v2.1.0   # 💡 MEANS → this is the image it is trying to pull

Events:
  Warning  Failed   2m  kubelet
           Failed to pull image "myrepo.example.com/myapp:v2.1.0":
           unauthorized: authentication required
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           # ⚠️ PROBLEM → registry requires a password, none was provided

  Warning  BackOff  90s  kubelet
           Back-off pulling image                # ⚠️ PROBLEM → Kubernetes keeps retrying
```

> **Other error messages you might see:**
> - `not found` → image name is wrong or that tag/version does not exist
> - `unauthorized` → registry needs credentials (username + password)
> - `connection refused` → the registry URL/address is wrong

## What It Looks Like When Fixed

```bash
$ kubectl describe pod my-app-8b7d-xxx -n default
```
```
Events:
  Normal  Pulling  30s  kubelet  Pulling image "myrepo.example.com/myapp:v2.1.0"
  Normal  Pulled   15s  kubelet  Successfully pulled image in 15s  # ✅ HEALTHY → image downloaded
  Normal  Created  14s  kubelet  Created container my-app
  Normal  Started  14s  kubelet  Started container my-app          # ✅ HEALTHY → app is running
```

---

# Issue 4 — Pod Stuck in Pending

## What You See (Broken)

```bash
$ kubectl get pods -n production
```
```
NAME                  READY   STATUS    RESTARTS   AGE
api-server-9c8d-xxx   0/1     Pending   0          10m
                               ↑↑↑↑↑↑↑  ↑
                               # ⚠️ PROBLEM → waiting for 10 minutes, never scheduled
                               # ⚠️ PROBLEM → RESTARTS=0 means it never even started
                               # 💡 MEANS  → no node in the cluster has enough resources
```

## Dig Deeper

```bash
$ kubectl describe pod api-server-9c8d-xxx -n production
```
```
Node:  <none>           # ⚠️ PROBLEM → not assigned to any server yet

Events:
  Warning  FailedScheduling  30s  scheduler
           0/4 nodes are available:
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           # ⚠️ PROBLEM → checked all 4 nodes and none can take this pod

           4 Insufficient memory.   # ⚠️ PROBLEM → all 4 nodes don't have enough RAM
           4 Insufficient cpu.      # ⚠️ PROBLEM → all 4 nodes don't have enough CPU
```

## Check Node Capacity

```bash
$ kubectl describe nodes | grep -A5 "Allocated resources"
```
```
Node: calico-prod-worker
  Allocated resources:
    Resource   Requests      Limits
    cpu        1850m / 2     ← 1850 out of 2000 CPU units used (92%)   # ⚠️ PROBLEM → almost full
    memory     1800Mi / 2Gi  ← 1800 out of 2048 MB used (88%)          # ⚠️ PROBLEM → almost full
```

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n production
```
```
NAME                  READY   STATUS    RESTARTS   AGE
api-server-9c8d-xxx   1/1     Running   0          1m   # ✅ HEALTHY → scheduled and running
```

---

# Issue 5 — Init Container Failing

## What You See (Broken)

```bash
$ kubectl get pods -n default
```
```
NAME                READY   STATUS     RESTARTS   AGE
web-app-7f8c-xxx    0/1     Init:0/1   3          8m
                             ↑↑↑↑↑↑↑↑
                             # ⚠️ PROBLEM → stuck in the init/setup step
                             # 💡 MEANS  → 0 out of 1 init containers have completed
                             # 💡 MEANS  → main app will never start until init passes
```

## Dig Deeper

```bash
$ kubectl describe pod web-app-7f8c-xxx -n default
```
```
Init Containers:
  wait-for-db:           # 💡 MEANS → name of the init container (setup step)
    State:    Terminated
      Reason: Error      # ⚠️ PROBLEM → setup step failed

Main Containers:
  web-app:
    State:  Waiting
      Reason: PodInitializing  # ⚠️ PROBLEM → main app blocked, waiting for init to pass
```

## Read Init Container Logs

```bash
$ kubectl logs web-app-7f8c-xxx -n default -c wait-for-db
#                                              ↑↑↑↑↑↑↑↑↑↑↑
#                                              specify the init container name with -c
```
```
Waiting for postgres-svc:5432...
Attempt  1/30: connecting... failed   # ⚠️ PROBLEM → cannot reach the database
Attempt  2/30: connecting... failed
Attempt 30/30: connecting... failed
Giving up after 30 attempts           # ⚠️ PROBLEM → database was never found
exit 1
```

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n default
```
```
NAME               READY   STATUS    RESTARTS   AGE
web-app-7f8c-xxx   1/1     Running   0          2m   # ✅ HEALTHY → init passed, main app running
```

---

# Issue 6 — Service Not Reachable

## Step 1 — Check Service Endpoints

```bash
$ kubectl get endpoints frontend-svc -n frontend
```
```
NAME           ENDPOINTS   AGE
frontend-svc   <none>      5d
               ↑↑↑↑↑↑
               # ⚠️ PROBLEM → <none> means NO pods are connected to this service
               # 💡 MEANS  → any request to this service will fail with "connection refused"
```

## Step 2 — See What Label the Service Expects

```bash
$ kubectl describe svc frontend-svc -n frontend
```
```
Selector:  app=frontend    # 💡 MEANS → service will only route to pods that have label: app=frontend
Endpoints: <none>          # ⚠️ PROBLEM → no pods with that label were found
```

## Step 3 — See What Labels the Pods Actually Have

```bash
$ kubectl get pods -n frontend --show-labels
```
```
NAME                  READY   STATUS    LABELS
frontend-6d9f-xk2pl   1/1     Running   app=web-frontend,version=v2
                                         ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                                         # ⚠️ PROBLEM → pod has "app=web-frontend"
                                         # Service expects "app=frontend"
                                         # They don't match → endpoints stay empty
```

## What It Looks Like When Fixed

```bash
$ kubectl get endpoints frontend-svc -n frontend
```
```
NAME           ENDPOINTS                       AGE
frontend-svc   10.244.1.5:80,10.244.2.3:80    5d
               ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
               # ✅ HEALTHY → 2 pod IPs listed, traffic will flow
```

---

# Issue 7 — DNS Resolution Failure

## Test DNS From Inside the Cluster

```bash
$ kubectl run dns-test --image=busybox --rm -it -- \
  nslookup frontend-svc.frontend.svc.cluster.local
```
```
# BROKEN — DNS not working:
nslookup: can't resolve 'frontend-svc.frontend.svc.cluster.local'
          ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
          # ⚠️ PROBLEM → DNS lookup failed, CoreDNS is broken or name is wrong

# HEALTHY — DNS working:
Server:    10.96.0.10
Address 1: 10.96.0.10

Name:      frontend-svc.frontend.svc.cluster.local
Address 1: 10.96.152.167    # ✅ HEALTHY → got an IP back, DNS is working
```

## Common DNS Name Mistakes

```bash
# ⚠️ WRONG — short name only works inside the same namespace
curl http://frontend-svc/

# ⚠️ WRONG — missing namespace in the name
curl http://frontend-svc.svc.cluster.local/

# ✅ CORRECT — full DNS name, works from any namespace
curl http://frontend-svc.frontend.svc.cluster.local/
#            ↑↑↑↑↑↑↑↑↑↑↑↑ ↑↑↑↑↑↑↑↑ ↑↑↑↑↑↑↑↑↑↑↑↑↑
#            service name   namespace  fixed domain
```

---

# Issue 8 — Ingress Not Routing (404 / 502)

## What You See (Broken)

```bash
$ kubectl get ingress -n frontend
```
```
NAME               HOSTS                  ADDRESS   PORTS   AGE
frontend-ingress   myapp.devopscab.com    <none>    80      5m
                                          ↑↑↑↑↑↑
                                          # ⚠️ PROBLEM → no IP address assigned
                                          # 💡 MEANS  → ingress controller is not running
                                          # Every request to this domain will fail
```

## Check Ingress Controller Logs

```bash
$ kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=20
```
```
# Causing 502 Bad Gateway:
[error] upstream "http://10.244.1.5:8080" unreachable    # ⚠️ PROBLEM → backend pod is down
[error] connect() failed (111: Connection refused)        # ⚠️ PROBLEM → wrong port number

# Causing 404 Not Found:
[warn]  no matching rule found for /api/users             # ⚠️ PROBLEM → path not in ingress rules
```

## What It Looks Like When Fixed

```bash
$ kubectl get ingress -n frontend
```
```
NAME               HOSTS                  ADDRESS         PORTS
frontend-ingress   myapp.devopscab.com    192.168.1.100   80
                                          ↑↑↑↑↑↑↑↑↑↑↑↑↑
                                          # ✅ HEALTHY → IP address assigned, ingress is working
```

---

# Issue 9 — Network Policy Blocking Traffic

## What You See (Broken)

```bash
$ kubectl exec backend-pod -n backend -- \
  curl -v --max-time 10 http://frontend-svc.frontend.svc.cluster.local
```
```
* Trying 10.96.152.167:80...
* Connection timed out after 10001ms     # ⚠️ PROBLEM → request timed out (not refused)
curl: (28) Operation timed out
```

> 💡 **Key difference:**
> - `Connection refused` = service/pod issue — responds immediately with error
> - `Connection timed out` = NetworkPolicy is silently dropping the packet — hangs and then fails

```bash
$ kubectl get networkpolicies -n frontend
```
```
NAME             POD-SELECTOR   AGE
deny-all         <none>         5d   # ⚠️ PROBLEM → deny-all blocks ALL traffic to this namespace
allow-same-ns    app=frontend   5d   # only allows traffic from within the same namespace
                                     # backend namespace traffic is BLOCKED
```

---

# Issue 10 — LoadBalancer EXTERNAL-IP Pending

## What You See (Broken)

```bash
$ kubectl get svc -n default
```
```
NAME         TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)
my-app-svc   LoadBalancer   10.96.45.123   <pending>     80:31234/TCP
                                           ↑↑↑↑↑↑↑↑↑
                                           # ⚠️ PROBLEM → no external IP, will wait forever on Kind
                                           # 💡 MEANS  → Kind has no cloud load balancer to assign
```

## Use Port-Forward Instead (Quick Fix on Kind)

```bash
$ kubectl port-forward svc/my-app-svc 8080:80 -n default
Forwarding from 127.0.0.1:8080 -> 80   # ✅ HEALTHY → access via http://localhost:8080
```

---

# Issue 11 — Node NotReady

## What You See (Broken)

```bash
$ kubectl get nodes
```
```
NAME                        STATUS     ROLES           AGE
calico-prod-control-plane   Ready      control-plane   72d   # ✅ HEALTHY
calico-prod-worker          Ready      <none>          72d   # ✅ HEALTHY
calico-prod-worker2         NotReady   <none>          72d   # ⚠️ PROBLEM → this node is offline
calico-prod-worker3         Ready      <none>          72d   # ✅ HEALTHY
```

## Dig Deeper

```bash
$ kubectl describe node calico-prod-worker2
```
```
Conditions:
  Type              Status   Reason
  MemoryPressure    False    KubeletHasSufficientMemory   # ✅ RAM is OK
  DiskPressure      True     KubeletHasDiskPressure       # ⚠️ PROBLEM → disk is full
  PIDPressure       False    KubeletHasSufficientPID      # ✅ Processes are OK
  Ready             False    KubeletNotReady              # ⚠️ PROBLEM → node is offline

Events:
  Warning  EvictionThresholdMet  2m  kubelet
           Attempting to reclaim ephemeral-storage        # ⚠️ PROBLEM → Kubernetes evicting pods
```

## What It Looks Like When Fixed

```bash
$ kubectl describe node calico-prod-worker2
```
```
Conditions:
  MemoryPressure    False   KubeletHasSufficientMemory   # ✅
  DiskPressure      False   KubeletHasSufficientDisk     # ✅
  PIDPressure       False   KubeletHasSufficientPID      # ✅
  Ready             True    KubeletReady                 # ✅ HEALTHY → node back online
```

---

# Issue 12 — Evicted Pods

## What You See (Broken)

```bash
$ kubectl get pods -A | grep Evicted
```
```
NAMESPACE   NAME                     READY   STATUS    AGE
default     api-server-7d6f9-abc12   0/1     Evicted   2h   # ⚠️ PROBLEM → forcefully removed
backend     flask-api-8c7d4-def34    0/1     Evicted   2h   # ⚠️ PROBLEM → forcefully removed
frontend    react-app-9b8e3-ghi56    0/1     Evicted   2h   # ⚠️ PROBLEM → forcefully removed
```

## Why It Happened

```bash
$ kubectl describe pod api-server-7d6f9-abc12 -n default
```
```
Status:   Failed
Reason:   Evicted
Message:  The node was low on resource: memory.
          Threshold quantity: 100Mi, available: 45Mi.      # ⚠️ PROBLEM → node had only 45MB free
          Container api-server was using 890Mi.            # ⚠️ ROOT CAUSE → no memory limit set
```

---

# Issue 13 — CPU Throttling (App Is Slow, No Errors)

## What You See (Broken)

```bash
$ kubectl top pods -n backend
```
```
NAME                CPU     MEMORY
flask-api-xxx       499m    180Mi
                    ↑↑↑↑
                    # ⚠️ PROBLEM → 499 out of 500 CPU units used (99.8%)
                    # 💡 MEANS  → app is being slowed down (throttled) by Kubernetes
                    # 💡 MEANS  → response time goes up, but NO errors, NO crashes
                    # This is why the app "feels slow" but no alerts fire
```

## What This Looks Like in New Relic APM

```
Transactions tab:
  /api/orders    response time: 2.8s    error rate: 0%   # ⚠️ PROBLEM → slow + no errors
  /api/health    response time: 2.1s    error rate: 0%   # ⚠️ PROBLEM → even health checks are slow
  /api/users     response time: 3.1s    error rate: 0%

# 💡 CPU throttling signature = HIGH response time + ZERO error rate
# If it was a code bug or crash, you would see errors too
```

## What It Looks Like When Fixed

```bash
$ kubectl top pods -n backend
```
```
NAME               CPU     MEMORY
flask-api-xxx      220m    180Mi    # ✅ HEALTHY → 220 out of 1000 CPU units (22%), plenty of room

# New Relic APM after fix:
/api/orders    response time: 0.2s    error rate: 0%   # ✅ HEALTHY → fast again
```

---

# Issue 14 — No Resource Limits Set

## What You See (Broken)

```bash
$ kubectl describe pod runaway-app-xxx -n default
```
```
Containers:
  runaway-app:
    Limits:   <none>   # ⚠️ PROBLEM → no ceiling — app can use ALL node resources
    Requests: <none>   # ⚠️ PROBLEM → scheduler has no idea how much this pod needs
```

```bash
$ kubectl top pods -n default
```
```
NAME                   CPU      MEMORY
runaway-app-xxx        3800m    7.8Gi    # ⚠️ PROBLEM → consuming almost entire node
other-service-yyy      10m      50Mi     # ⚠️ PROBLEM → starved, barely getting any CPU
database-zzz           5m       30Mi     # ⚠️ PROBLEM → database starved, all queries slow
```

---

# Issue 15 — HPA Not Scaling

## What You See (Broken)

```bash
$ kubectl get hpa -n production
```
```
NAME      REFERENCE            TARGETS         MINPODS   MAXPODS   REPLICAS
app-hpa   Deployment/my-app    <unknown>/70%   2         10        2
                               ↑↑↑↑↑↑↑↑↑
                               # ⚠️ PROBLEM → <unknown> means HPA cannot read CPU data
                               # 💡 MEANS  → Metrics Server is down or missing
                               # 💡 MEANS  → pods will stay at 2 even under massive load
```

## Check Why

```bash
$ kubectl describe hpa app-hpa -n production
```
```
Events:
  Warning  FailedGetScale  2m  horizontal-pod-autoscaler
           failed to get cpu utilization:
           unable to fetch metrics from resource metrics API:
           the server is currently unable to handle the request
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           # ⚠️ PROBLEM → Metrics Server is not running or not accessible
```

## What It Looks Like When Fixed

```bash
$ kubectl get hpa -n production
```
```
NAME      REFERENCE            TARGETS    MINPODS   MAXPODS   REPLICAS
app-hpa   Deployment/my-app    85%/70%    2         10        6
                               ↑↑↑↑↑↑↑             ↑↑        ↑
                               # ✅ HEALTHY → actual CPU% shown
                               # ✅ HEALTHY → maxPods is 10
                               # ✅ HEALTHY → scaled UP to 6 replicas because 85% > 70% threshold
```

---

# Issue 16 — Missing Secret or ConfigMap

## What You See (Broken)

```bash
$ kubectl get pods -n backend
```
```
NAME                   READY   STATUS                       RESTARTS   AGE
api-server-7d6f9-xxx   0/1     CreateContainerConfigError   0          2m
                                ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                                # ⚠️ PROBLEM → cannot create the container at all
                                # 💡 MEANS  → a required Secret or ConfigMap is missing
```

## Find the Missing Config

```bash
$ kubectl describe pod api-server-7d6f9-xxx -n backend
```
```
Events:
  Warning  Failed  30s  kubelet
           Error: secret "db-credentials" not found
                  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                  # ⚠️ PROBLEM → deployment asks for this secret, but it was never created
```

```bash
$ kubectl get secrets -n backend
```
```
NAME               TYPE     DATA   AGE
default-token-xyz  Opaque   3      72d
# ⚠️ PROBLEM → "db-credentials" is NOT in this list → it is missing
```

## What It Looks Like When Fixed

```bash
$ kubectl get secrets -n backend
```
```
NAME               TYPE     DATA   AGE
db-credentials     Opaque   2      5s    # ✅ HEALTHY → secret now exists

$ kubectl get pods -n backend
NAME                   READY   STATUS    RESTARTS   AGE
api-server-7d6f9-xxx   1/1     Running   0          30s   # ✅ HEALTHY → pod now running
```

---

# Issue 17 — Wrong Environment Variable

## What You See (Broken)

```bash
$ kubectl exec api-server-xxx -n backend -- env | grep DB_HOST
```
```
DB_HOST=localhost
         ↑↑↑↑↑↑↑↑↑
         # ⚠️ PROBLEM → app is connecting to itself (no database on localhost)
         # 💡 MEANS  → database is in a different pod, needs the Kubernetes service name
```

## What the App Logs Show

```bash
$ kubectl logs api-server-xxx -n backend
```
```
2026-04-12 ERROR  Connection refused: localhost:5432   # ⚠️ PROBLEM → nothing listening on localhost
2026-04-12 ERROR  Cannot connect to database. All queries failing.
```

## What It Looks Like When Fixed

```bash
$ kubectl exec api-server-xxx -n backend -- env | grep DB_HOST
```
```
DB_HOST=postgres-svc.database.svc.cluster.local   # ✅ HEALTHY → correct Kubernetes service name

$ kubectl logs api-server-xxx -n backend
2026-04-12 INFO  Connected to postgres-svc.database.svc.cluster.local:5432   # ✅ HEALTHY
2026-04-12 INFO  Database ready. Connection pool initialized with 5 connections.
```

---

# Issue 18 — Liveness Probe Failing

## What You See (Broken)

```bash
$ kubectl describe pod my-app-xxx -n default
```
```
Containers:
  my-app:
    Liveness:  http-get http://:8080/healthz   # ⚠️ PROBLEM → probe is calling /healthz
    #                                                         but app only has /health (no z)
    Restart Count: 12                           # ⚠️ PROBLEM → restarted 12 times unnecessarily

Events:
  Warning  Unhealthy  30s  kubelet
           Liveness probe failed: HTTP probe failed with statuscode: 404
           # ⚠️ PROBLEM → /healthz returns 404 because it doesn't exist
  Warning  Killing    30s  kubelet
           Container my-app failed liveness probe, will be restarted
           # ⚠️ PROBLEM → Kubernetes kills and restarts a perfectly healthy app
```

## What It Looks Like When Fixed

```bash
$ kubectl describe pod my-app-xxx -n default
```
```
    Liveness:  http-get http://:8080/health    # ✅ HEALTHY → correct path (no z)
    Restart Count: 0                           # ✅ HEALTHY → no unnecessary restarts

Events:
  Normal  Started  5m  kubelet  Started container my-app   # ✅ HEALTHY → no Warning events
```

---

# Issue 19 — Readiness Probe Failing

## What You See (Broken)

```bash
$ kubectl get pods -n backend
```
```
NAME                   READY   STATUS    RESTARTS   AGE
api-server-7d6f9-xxx   0/1     Running   0          5m
                        ↑↑↑
                        # ⚠️ PROBLEM → Running but 0/1 READY
                        # 💡 MEANS  → pod is alive but Kubernetes will NOT send it any traffic
                        # 💡 MEANS  → service endpoints will show <none>
```

## Why It Happens

```bash
$ kubectl describe pod api-server-7d6f9-xxx -n backend
```
```
    Readiness: http-get http://:8080/ready   delay=5s   # ⚠️ PROBLEM → probes at 5 seconds
                                                         # app takes 30 seconds to start
                                                         # probe fires before app is ready
Events:
  Warning  Unhealthy  4m  kubelet
           Readiness probe failed: connect: connection refused
           # ⚠️ PROBLEM → app not listening yet at 5 seconds
```

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n backend
```
```
NAME                   READY   STATUS    RESTARTS   AGE
api-server-7d6f9-xxx   1/1     Running   0          2m   # ✅ HEALTHY → 1/1 = ready for traffic

$ kubectl get endpoints api-server-svc -n backend
NAME             ENDPOINTS
api-server-svc   10.244.1.5:8080   # ✅ HEALTHY → pod IP listed = traffic flowing to it
```

---

# Issue 20 — Using :latest Image Tag

## The Problem Illustrated

```bash
# Two pods, same image tag :latest, but different actual images:

$ kubectl describe pod my-app-worker-1-xxx -n default
  Image ID: sha256:abc123def456...    # cached 3 days ago — old version

$ kubectl describe pod my-app-worker-2-xxx -n default
  Image ID: sha256:fff999aaa111...    # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑ pulled today — new version
             ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
             # ⚠️ PROBLEM → two different SHAs under the same :latest tag
             # 💡 MEANS  → Pod 1 runs old code, Pod 2 runs new code
             # 💡 MEANS  → some user requests work, some fail — random and hard to debug
```

---

# Issue 21 — PVC Stuck in Pending

## What You See (Broken)

```bash
$ kubectl get pvc -n database
```
```
NAME           STATUS    STORAGECLASS   AGE
postgres-pvc   Pending   fast-ssd       10m
               ↑↑↑↑↑↑↑   ↑↑↑↑↑↑↑↑
               # ⚠️ PROBLEM → pending for 10 minutes (should bind in seconds)
               # ⚠️ PROBLEM → StorageClass "fast-ssd" does not exist in this cluster
```

## Find the Cause

```bash
$ kubectl describe pvc postgres-pvc -n database
```
```
Events:
  Warning  ProvisioningFailed  9m  persistentvolume-controller
           storageclass.storage.k8s.io "fast-ssd" not found
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           # ⚠️ ROOT CAUSE → the StorageClass referenced in PVC does not exist
```

```bash
$ kubectl get storageclass
```
```
NAME                 PROVISIONER
standard (default)   rancher.io/local-path    # ✅ This exists but PVC asks for "fast-ssd"
# "fast-ssd" is NOT in this list              # ⚠️ PROBLEM → wrong name in PVC YAML
```

## What It Looks Like When Fixed

```bash
$ kubectl get pvc -n database
```
```
NAME           STATUS   VOLUME          CAPACITY   STORAGECLASS   AGE
postgres-pvc   Bound    pvc-abc-xyz     10Gi       standard       5s
               ↑↑↑↑↑
               # ✅ HEALTHY → Bound means storage allocated and ready to use
```

---

# Issue 24 — Deployment Rollout Stuck

## What You See (Broken)

```bash
$ kubectl rollout status deployment/my-app -n production
```
```
Waiting for deployment "my-app" rollout to finish:
1 out of 2 new replicas have been updated...
↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# ⚠️ PROBLEM → stuck here for 10+ minutes
# 💡 MEANS  → new version pod is unhealthy
# 💡 MEANS  → old version stays running (good) but new version cannot deploy
```

```bash
$ kubectl get pods -n production
```
```
NAME                     READY   STATUS             RESTARTS   AGE
my-app-OLD-7d6f9-abc12   1/1     Running            0          2d    # old version, still alive
my-app-NEW-8e7g0-def34   0/1     CrashLoopBackOff   5          5m    # ⚠️ PROBLEM → new version crashing
                                  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                                  # New pod crashes → rollout blocked
                                  # Rollout will never finish until new pod is healthy
```

---

# Issue 25 — Rollback

## See All Deployed Versions

```bash
$ kubectl rollout history deployment/my-app -n production
```
```
REVISION   CHANGE-CAUSE
1          version 1.0.0   # old, working
2          version 1.1.0   # working — this is what we want to go back to
3          version 2.0.0   # ⚠️ CURRENT → broken in production, need to rollback
```

## After Rollback

```bash
$ kubectl rollout undo deployment/my-app -n production --to-revision=2
deployment.apps/my-app rolled back   # rollback started

$ kubectl rollout status deployment/my-app -n production
deployment "my-app" successfully rolled out   # ✅ HEALTHY → back to version 1.1.0
```

---

# Issue 27 — No Logs in New Relic

## What You See (Broken)

```bash
$ kubectl get pods -n newrelic | grep logging
```
```
NAME                              READY   STATUS             RESTARTS   AGE
nri-bundle-newrelic-logging-xxx   0/1     CrashLoopBackOff   8          1h
                                           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                                           # ⚠️ PROBLEM → log forwarder is crashing
                                           # 💡 MEANS  → no pod logs are going to New Relic
```

```bash
$ kubectl logs nri-bundle-newrelic-logging-xxx -n newrelic --previous
```
```
[error] HTTP status: 403 Forbidden          # ⚠️ PROBLEM → New Relic rejected the request
[error] License key rejected by New Relic   # ⚠️ ROOT CAUSE → wrong license key in config
```

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n newrelic | grep logging
```
```
NAME                              READY   STATUS    RESTARTS   AGE
nri-bundle-newrelic-logging-xxx   1/1     Running   0          5m   # ✅ HEALTHY

$ kubectl logs nri-bundle-newrelic-logging-xxx -n newrelic --tail=5
[info]  Flushing 250 log records to New Relic     # ✅ HEALTHY → logs being sent
[info]  HTTP status: 202                          # ✅ HEALTHY → 202 = accepted by New Relic
```

---

# Issue 30 — RBAC Permission Denied

## What the App Logs Show (Broken)

```bash
$ kubectl logs monitoring-agent-xxx -n monitoring
```
```
2026-04-12 ERROR  k8s_client: failed to list pods
                  User "system:serviceaccount:monitoring:my-agent"
                  cannot list resource "pods" in API group ""
                  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                  # ⚠️ PROBLEM → this service account has no permission to list pods
                  Status: 403 Forbidden
```

## Check if Role Binding Exists

```bash
$ kubectl get clusterrolebindings | grep my-agent
```
```
# No output
# ⚠️ PROBLEM → no ClusterRoleBinding exists for this service account
```

## What It Looks Like When Fixed

```bash
$ kubectl get clusterrolebindings | grep my-agent
```
```
my-agent-reader   ClusterRole/pod-reader   1d   # ✅ HEALTHY → binding exists

$ kubectl logs monitoring-agent-xxx -n monitoring
2026-04-12 INFO  Successfully listed 45 pods across 8 namespaces   # ✅ HEALTHY → access granted
```

---

# Summary — Problem vs Healthy at a Glance

| Status You See | What It Means | First Command to Run |
|---|---|---|
| `CrashLoopBackOff` | App crashes every time it starts | `kubectl logs <pod> --previous` |
| `OOMKilled` | App used more memory than allowed | `kubectl describe pod <pod>` → look for Exit Code 137 |
| `ImagePullBackOff` | Cannot download Docker image | `kubectl describe pod <pod>` → read Events section |
| `Pending` | No server available to run the pod | `kubectl describe pod <pod>` → read Events section |
| `Init:0/1` | Setup step before app failed | `kubectl logs <pod> -c <init-container-name>` |
| `0/1 Running` | Running but not accepting traffic | `kubectl describe pod <pod>` → check Readiness probe |
| `Evicted` | Server ran out of resources | `kubectl describe pod <pod>` → read Message field |
| `<none>` in Endpoints | No pods connected to service | `kubectl describe svc <svc>` vs pod labels |
| `<unknown>` in HPA | Cannot read CPU metrics | `kubectl top pods` — if fails, install Metrics Server |
| `<pending>` in LoadBalancer | No cloud LB available | Use `kubectl port-forward` instead on Kind |

---

*Last updated: April 2026 | Cluster: kind-calico-prod | Read alongside: K8s_issues.md*
