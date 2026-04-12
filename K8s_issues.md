# Kubernetes Issues — Plain English Guide

> Think of Kubernetes like a restaurant kitchen.
> - **Node** = a chef's workstation
> - **Pod** = a dish being prepared
> - **Container** = the actual cooking happening inside the dish
> - **Service** = the waiter who delivers the dish to the right table
> - **Deployment** = the recipe that says how many dishes to make

---

## Where to Start — Every Single Time

Before anything else, run these 3 commands. They answer:
- **What is broken?**
- **Why is it broken?**
- **What did the app say before it died?**

```bash
# 1. Show me everything that is NOT running
kubectl get pods -A | grep -v Running | grep -v Completed

# 2. Show me full details of the broken pod
kubectl describe pod <pod-name> -n <namespace>

# 3. Show me the last logs before it crashed
kubectl logs <pod-name> -n <namespace> --previous
```

---

# Issue 1 — CrashLoopBackOff

## What Is Happening?

Imagine you hired a new chef (your app). The chef walks in, tries to start cooking, something goes wrong, and they walk out. You call them back. They walk in again, same thing happens. Over and over.

That is CrashLoopBackOff — **your app keeps starting and crashing, over and over again.**

Kubernetes waits longer each time before restarting:
- 1st crash → wait 10 seconds
- 2nd crash → wait 20 seconds
- 3rd crash → wait 40 seconds
- After many crashes → wait 5 minutes

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME                READY   STATUS              RESTARTS   AGE
my-app-xxx          0/1     CrashLoopBackOff    6          15m
```

- `0/1` → pod is NOT ready (0 containers running out of 1)
- `CrashLoopBackOff` → crashing and restarting
- `RESTARTS: 6` → already crashed 6 times

## How to Find the Cause

```bash
# Step 1 — Find the exit code (tells you WHY it crashed)
kubectl describe pod my-app-xxx -n <namespace>
```

Look for this section in the output:
```
Last State: Terminated
  Reason:    Error
  Exit Code: 1        ← this number tells you the reason
```

**Exit Code meaning:**
- `Exit Code: 1`   → The app itself crashed (code bug, wrong config, DB not reachable)
- `Exit Code: 137` → App was killed because it used too much memory
- `Exit Code: 139` → App hit a fatal code error (segfault)

```bash
# Step 2 — Read the actual crash message
# Use --previous to see logs from the LAST run (not current)
kubectl logs my-app-xxx -n <namespace> --previous
```

## Common Causes and Fix

| Cause | What logs say | Fix |
|---|---|---|
| DB not reachable | `Connection refused: postgres:5432` | Check DB pod is running |
| Missing config | `Environment variable DB_HOST not set` | Add the missing env var |
| App code bug | `NullPointerException` or `Error: cannot read property` | Fix the bug, redeploy |
| Wrong startup command | `bash: myapp: command not found` | Fix the command in deployment |

```bash
# Fix — restart the deployment after fixing the issue
kubectl rollout restart deployment <name> -n <namespace>
```

---

# Issue 2 — OOMKilled

## What Is Happening?

Your app is like a chef working at a small table (memory limit). The chef keeps piling up more and more ingredients on the table. When the table overflows, the kitchen manager (Kubernetes) **flips the table and sends the chef home** — that is OOMKilled.

OOM = Out Of Memory. Killed = forcefully terminated.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME              READY   STATUS      RESTARTS   AGE
flask-api-xxx     0/1     OOMKilled   3          20m
```

OR it shows as CrashLoopBackOff with Exit Code 137:
```
Last State: Terminated
  Reason:    OOMKilled    ← killed by kernel, not by app
  Exit Code: 137
```

## How to Find the Cause

```bash
# See how much memory the pod is using right now
kubectl top pod <pod-name> -n <namespace>
```

```
NAME          CPU   MEMORY
flask-api-xxx  45m   251Mi   ← using 251Mi
```

Then check what the limit is:
```bash
kubectl describe pod <pod-name> -n <namespace>
```

```
Limits:
  memory: 256Mi    ← limit is 256Mi, pod uses 251Mi = about to be killed
```

## Fix

```yaml
# In your deployment YAML, increase the memory limit
resources:
  requests:
    memory: "256Mi"   # minimum memory guaranteed
  limits:
    memory: "512Mi"   # maximum allowed — increase this
```

```bash
# Apply and restart
kubectl rollout restart deployment <name> -n <namespace>
```

---

# Issue 3 — ImagePullBackOff

## What Is Happening?

Before your app can run, Kubernetes needs to download the app's Docker image (like downloading software). If it cannot find the image or is not allowed to download it — the pod never starts.

Think of it like: you ordered food but gave the wrong delivery address. The delivery person keeps trying and failing.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME          READY   STATUS             RESTARTS   AGE
my-app-xxx    0/1     ImagePullBackOff   0          3m
```

## How to Find the Cause

```bash
kubectl describe pod my-app-xxx -n <namespace>
```

Look at the **Events** section at the bottom:
```
Events:
  Warning  Failed  2m  kubelet  Failed to pull image "myrepo/myapp:v2.1":
                                unauthorized: authentication required
                                ← this means: registry needs a password
```

**Other error messages and what they mean:**
- `not found` → you typed the wrong image name or wrong version tag
- `unauthorized` → you have no permission to pull from this registry
- `connection refused` → the registry URL is wrong

## Fix

```bash
# Fix 1 — Typo in image name, correct it
kubectl set image deployment/<name> <container>=myrepo/myapp:v2.1 -n <namespace>

# Fix 2 — Private registry needs credentials
# Create a secret with your registry login
kubectl create secret docker-registry my-registry-secret \
  --docker-server=myrepo.example.com \
  --docker-username=myuser \
  --docker-password=mypassword \
  -n <namespace>

# Tell the deployment to use this secret
kubectl patch deployment <name> -n <namespace> \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"my-registry-secret"}]}}}}'
```

---

# Issue 4 — Pod Stuck in Pending

## What Is Happening?

Your pod is created but **no server (node) can take it**. It is like a new customer arriving at a restaurant but every table is full — they just wait at the door.

The pod has not even started yet. It is just waiting for a spot.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME              READY   STATUS    RESTARTS   AGE
api-server-xxx    0/1     Pending   0          10m
                                               ← waiting for 10 minutes = problem
```

Note: `RESTARTS: 0` — the app never even started once.

## How to Find the Cause

```bash
# This is the MOST important command for Pending pods
kubectl describe pod <pod-name> -n <namespace>
```

Look at the **Events** section at the bottom:
```
Events:
  Warning  FailedScheduling  30s  scheduler
           0/4 nodes are available:
           4 Insufficient memory.    ← all 4 nodes are out of memory
           4 Insufficient cpu.       ← all 4 nodes are out of CPU
```

OR:
```
           node(s) didn't match node selector   ← pod needs specific node labels that don't exist
```

## Fix

```bash
# Check how full your nodes are
kubectl describe nodes | grep -A5 "Allocated resources"
```

```
# If nodes are full — reduce what the pod asks for:
resources:
  requests:
    cpu: "100m"      ← lower this (was 500m)
    memory: "128Mi"  ← lower this (was 512Mi)
```

---

# Issue 5 — Init Container Failing

## What Is Happening?

Some pods have a "setup step" that runs before the main app. This is called an init container. Think of it like a prep cook who sets up the kitchen before the main chef arrives.

If the prep cook fails — the main chef never comes in. The pod stays stuck forever.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME          READY   STATUS     RESTARTS   AGE
web-app-xxx   0/1     Init:0/1   3          8m
                      ^^^^^^^^
                      ← stuck in init step (0 of 1 init containers done)
```

## How to Find the Cause

```bash
# Step 1 — Find the init container name
kubectl describe pod <pod-name> -n <namespace>
# Look for "Init Containers:" section → note the name

# Step 2 — Read the init container logs (specify with -c flag)
kubectl logs <pod-name> -n <namespace> -c <init-container-name>
```

```
# Common output:
Waiting for database at postgres-svc:5432...
Attempt 1: failed to connect
Attempt 2: failed to connect
...
Giving up after 30 attempts   ← init failed because DB is not running
```

## Fix

```bash
# Check if the dependency (DB) is actually running
kubectl get pods -n <namespace> | grep db
kubectl logs <db-pod-name> -n <namespace>

# Fix the DB first, then the init container will pass automatically
```

---

# Issue 6 — Service Not Reachable

## What Is Happening?

In Kubernetes, a Service acts like a phone operator — it routes calls to the right pod. If the service cannot find any pods to route to, all calls fail.

The most common reason: **the service is looking for pods with label `app=frontend` but the pods have label `app=web-frontend`** — a small typo causes complete failure.

## How to Spot It

```bash
# Check if the service has any pods behind it
kubectl get endpoints <service-name> -n <namespace>
```

```
NAME           ENDPOINTS   AGE
frontend-svc   <none>      5d
               ^^^^^^
               ← <none> means zero pods are connected to this service
               ← all traffic to this service will fail
```

## How to Find the Cause

```bash
# Step 1 — See what label the service is looking for
kubectl describe svc <service-name> -n <namespace>
```

```
Selector: app=frontend    ← service expects pods with this label
```

```bash
# Step 2 — See what labels the pods actually have
kubectl get pods -n <namespace> --show-labels
```

```
NAME               LABELS
frontend-xxx       app=web-frontend   ← POD has this label
                   ^^^^^^^^^^^^^^^^
                   ← "web-frontend" ≠ "frontend"  ← MISMATCH = root cause
```

## Fix

```bash
# Fix the service selector to match the pod label
kubectl patch svc <service-name> -n <namespace> \
  -p '{"spec":{"selector":{"app":"web-frontend"}}}'
```

---

# Issue 7 — DNS Resolution Failure

## What Is Happening?

Every service in Kubernetes has a name (like a website URL). When your app tries to call another service by name, it uses DNS to find the correct IP address.

If DNS is broken — the app cannot find any other service. It is like trying to call someone but the phone book is missing.

## How to Spot It

App logs will say:
```
Error: getaddrinfo ENOTFOUND frontend-svc
Error: Could not resolve host: postgres-svc
Error: Name or service not known
```

## How to Find the Cause

```bash
# Test DNS from inside the cluster
kubectl run dns-test --image=busybox --rm -it -- \
  nslookup kubernetes.default.svc.cluster.local

# If this fails → CoreDNS is broken
# Check CoreDNS pods
kubectl get pods -n kube-system | grep coredns
```

**Most common mistake — wrong service DNS name format:**

```
# WRONG — only works within the same namespace
http://frontend-svc

# WRONG — missing namespace
http://frontend-svc.svc.cluster.local

# CORRECT — full name, works from any namespace
http://frontend-svc.frontend.svc.cluster.local
#            ↑service  ↑namespace  ↑domain
```

## Fix

```bash
# If CoreDNS is crashing, restart it
kubectl rollout restart deployment coredns -n kube-system

# If the app is using wrong hostname, update the env var
kubectl set env deployment/<app-name> -n <namespace> \
  DB_HOST=postgres-svc.database.svc.cluster.local
```

---

# Issue 8 — Ingress Not Routing (404 or 502 Error)

## What Is Happening?

Ingress is the front door of your application — it receives traffic from the internet and sends it to the right service. When it does not work:
- **404** = the door exists but the room behind it does not
- **502** = the room exists but the person inside is not responding

## How to Spot It

```bash
kubectl get ingress -n <namespace>
```

```
NAME               HOSTS                   ADDRESS   PORTS
frontend-ingress   myapp.devopscab.com     <none>    80
                                           ^^^^^^
                                           ← no IP = ingress controller not installed or broken
```

## How to Find the Cause

```bash
# Check if ingress controller is running
kubectl get pods -n ingress-nginx

# Read ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=30
```

```
# 502 error in logs:
upstream unreachable  ← backend pod is crashing or wrong port

# 404 error in logs:
no matching rule for path /api/users  ← ingress path rule is missing or wrong
```

## Fix

| Error | Cause | Fix |
|---|---|---|
| 404 | Wrong path or hostname in ingress | Fix the `host` or `path` in ingress YAML |
| 502 | Backend pod is down or wrong port | Fix the pod issue first, then check `targetPort` |
| No IP address | Ingress controller missing | Install nginx ingress controller |

```bash
# Test backend service directly (skip ingress completely)
kubectl port-forward svc/<service-name> 8080:80 -n <namespace>
curl http://localhost:8080
# If this works → problem is in ingress config
# If this fails → problem is in the backend pod/service
```

---

# Issue 9 — Network Policy Blocking Traffic

## What Is Happening?

Network Policies are like security guards between rooms. If you add a "deny all" policy — no room can talk to any other room.

The tricky part: **the app shows as Running and Healthy, but all requests just time out silently.**

## How to Spot It

```bash
# Test connection between two pods
kubectl exec <source-pod> -n <namespace> -- \
  curl -v --max-time 10 http://frontend-svc.frontend.svc.cluster.local
```

```
* Trying 10.96.152.167:80...
* Connection timed out after 10000ms   ← timeout (not refused)
```

Timeout = NetworkPolicy is silently dropping packets (not connection refused which would be instant).

## Fix

```bash
# Allow traffic from backend to frontend namespace
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-backend
  namespace: frontend
spec:
  podSelector: {}
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: backend
EOF
```

---

# Issue 10 — LoadBalancer IP Stays as Pending

## What Is Happening?

On cloud providers (AWS, GCP), when you create a LoadBalancer service, Kubernetes asks the cloud to create a real Load Balancer and gives you an IP. On local clusters like **Kind or Minikube**, there is no cloud — so the IP never comes.

## How to Spot It

```bash
kubectl get svc -n <namespace>
```

```
NAME       TYPE           CLUSTER-IP    EXTERNAL-IP   PORT(S)
my-app     LoadBalancer   10.96.45.1    <pending>     80:31234/TCP
                                        ^^^^^^^^^
                                        ← waiting forever on Kind/Minikube
```

## Fix for Kind (Local Cluster)

```bash
# Use port-forward instead to access the service locally
kubectl port-forward svc/my-app 8080:80 -n <namespace>
# Now access via: http://localhost:8080
```

---

# Issue 11 — Node NotReady

## What Is Happening?

A node (server) has gone offline or is in trouble. All pods on that node are either evicted (removed) or stuck. Think of it like a chef's entire workstation breaking down.

## How to Spot It

```bash
kubectl get nodes
```

```
NAME                      STATUS     ROLES    AGE
calico-prod-worker        Ready      <none>   72d   ← ✅ healthy
calico-prod-worker2       NotReady   <none>   72d   ← ⚠️ offline
calico-prod-worker3       Ready      <none>   72d   ← ✅ healthy
```

## How to Find the Cause

```bash
kubectl describe node calico-prod-worker2
```

Look for **Conditions** section:
```
DiskPressure:    True    ← node disk is full
MemoryPressure:  True    ← node RAM is full
Ready:           False   ← node is offline
```

## Fix

```bash
# Move all pods off this node safely
kubectl drain calico-prod-worker2 --ignore-daemonsets --delete-emptydir-data

# After fixing the node (clear disk, free memory)
kubectl uncordon calico-prod-worker2   ← allow pods back on this node
```

---

# Issue 12 — Evicted Pods

## What Is Happening?

When a node runs out of memory or disk, Kubernetes forcefully removes some pods to save the node. These pods show as **Evicted** — they are dead and will not restart on their own.

## How to Spot It

```bash
kubectl get pods -A | grep Evicted
```

```
NAMESPACE   NAME                   READY   STATUS    AGE
default     api-server-xxx         0/1     Evicted   2h
backend     flask-api-xxx          0/1     Evicted   2h
```

## Fix

```bash
# Delete all evicted pods (they don't auto-clean up)
kubectl get pods -A | grep Evicted | \
  awk '{print "kubectl delete pod " $2 " -n " $1}' | bash

# The deployment will create new pods automatically
# Fix the underlying node issue (disk/memory) to prevent future evictions
```

---

# Issue 13 — CPU Throttling (App Is Slow But Looks Healthy)

## What Is Happening?

This is the trickiest issue — **no alerts fire, pod shows Running, zero errors — but the app feels slow.**

Think of a chef limited to using only 1 hand. They can do the work but everything takes 3x longer. The chef is not sick (no errors), just limited (throttled).

CPU throttling happens when:
- Your pod is using 100% of its CPU limit
- Kubernetes slows it down instead of killing it
- Response time goes up, but no crashes or errors

## How to Spot It

```bash
kubectl top pods -n <namespace>
```

```
NAME          CPU    MEMORY
my-app-xxx    499m   180Mi   ← using 499m out of 500m limit (99%)
```

In New Relic APM:
```
/api/orders    response time: 2.8s    error rate: 0%
/api/health    response time: 2.1s    error rate: 0%
←── Slow response time + zero errors = classic CPU throttling signature
```

## Fix

```yaml
# Increase CPU limit in deployment YAML
resources:
  requests:
    cpu: "200m"
  limits:
    cpu: "1000m"   ← increase from 500m to 1000m
```

---

# Issue 14 — No Resource Limits Set

## What Is Happening?

If a pod has no limits, it can eat up ALL the CPU and memory on the node — starving every other pod on that node.

Like a chef who takes up every single cooking station, leaving no room for others.

## How to Spot It

```bash
kubectl describe pod <pod-name> -n <namespace>
```

```
Limits:   <none>    ← no limits set = can use unlimited resources
Requests: <none>    ← no requests set = scheduler has no guidance
```

## Fix

```yaml
# Always add this to every container in every deployment
resources:
  requests:
    cpu: "100m"      # minimum guaranteed
    memory: "128Mi"  # minimum guaranteed
  limits:
    cpu: "500m"      # maximum allowed
    memory: "256Mi"  # maximum allowed
```

---

# Issue 15 — HPA Not Scaling

## What Is Happening?

HPA (Horizontal Pod Autoscaler) automatically adds more pods when your app is busy. But it needs a **Metrics Server** to know how busy the app is.

If Metrics Server is not installed or broken — HPA cannot see CPU usage — so it never scales. Your app stays slow under load instead of spinning up more pods.

## How to Spot It

```bash
kubectl get hpa -n <namespace>
```

```
NAME     REFERENCE          TARGETS         MINPODS   MAXPODS   REPLICAS
app-hpa  Deployment/my-app  <unknown>/70%   2         10        2
                            ^^^^^^^^^
                            ← <unknown> means HPA cannot read CPU data
                            ← pods will never scale even under heavy load
```

## Fix

```bash
# Check if Metrics Server is running
kubectl get pods -n kube-system | grep metrics-server

# Install Metrics Server if missing
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For Kind clusters — also add this flag (Kind uses self-signed certs)
kubectl patch deployment metrics-server -n kube-system \
  --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

# Issue 16 — Missing Secret or ConfigMap

## What Is Happening?

Your app needs passwords, API keys, or configuration values at startup. These are stored in Kubernetes **Secrets** and **ConfigMaps**. If they are missing — the app cannot start at all.

Like a chef arriving but the recipe book and ingredients list are missing.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME          READY   STATUS                       RESTARTS   AGE
api-xxx       0/1     CreateContainerConfigError   0          2m
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^
                      ← cannot even create the container — config is missing
```

## How to Find the Cause

```bash
kubectl describe pod <pod-name> -n <namespace>
```

```
Events:
  Warning  Failed  30s  kubelet
           Error: secret "db-credentials" not found   ← this secret is missing
```

## Fix

```bash
# Create the missing secret
kubectl create secret generic db-credentials \
  --from-literal=DB_PASSWORD=mypassword \
  --from-literal=DB_USER=admin \
  -n <namespace>

# Restart the pod
kubectl rollout restart deployment <name> -n <namespace>
```

---

# Issue 17 — Wrong Environment Variable

## What Is Happening?

The app has the right config — but the value is wrong. For example, DB_HOST is set to `localhost` instead of the actual database service name. The app starts fine but fails when it tries to connect.

## How to Spot It

```bash
# Check what the running pod actually sees
kubectl exec <pod-name> -n <namespace> -- env | grep DB
```

```
DB_HOST=localhost    ← app is trying to connect to itself (no DB there)
DB_PORT=5432
```

## Fix

```bash
# Update the environment variable
kubectl set env deployment/<name> -n <namespace> \
  DB_HOST=postgres-svc.database.svc.cluster.local

# Restart pods
kubectl rollout restart deployment <name> -n <namespace>
```

---

# Issue 18 — Liveness Probe Failing

## What Is Happening?

Kubernetes checks if your app is alive using a Liveness Probe — it calls a health check URL. If the URL returns an error, Kubernetes thinks the app is dead and **restarts it**.

If you configure the wrong URL, Kubernetes keeps restarting a perfectly healthy app.

## How to Spot It

```bash
kubectl describe pod <pod-name> -n <namespace>
```

```
Events:
  Warning  Unhealthy  30s  kubelet
           Liveness probe failed: HTTP probe failed with statuscode: 404
           ← Kubernetes called /healthz but the app only has /health
  Warning  Killing    30s  kubelet
           Container failed liveness probe, will be restarted
           ← app gets killed and restarted unnecessarily
```

## Fix

```yaml
livenessProbe:
  httpGet:
    path: /health      ← must exactly match a URL your app responds to
    port: 8080
  initialDelaySeconds: 30   ← wait 30s before first check (give app time to start)
  periodSeconds: 10
  failureThreshold: 3
```

---

# Issue 19 — Readiness Probe Failing

## What Is Happening?

Similar to Liveness Probe, but the Readiness Probe tells Kubernetes: "is this pod ready to receive traffic?"

If the probe fails, the pod gets **removed from the service** — no traffic reaches it — but it stays running.

Most common reason: **the probe fires too early** before the app has finished starting up.

## How to Spot It

```bash
kubectl get pods -n <namespace>
```

```
NAME          READY   STATUS    RESTARTS   AGE
api-xxx       0/1     Running   0          5m
              ^^^
              ← 0/1 = pod is Running but NOT READY
              ← 0 traffic is going to this pod
              ← service endpoints will show <none>
```

## Fix

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 15    ← wait 15 seconds before first check
  periodSeconds: 5
  failureThreshold: 6        ← allow 6 failures before removing from service
```

---

# Issue 20 — Using `:latest` Image Tag

## What Is Happening?

`:latest` means "give me the newest version". The problem: different nodes in your cluster may have **different cached versions** of "latest". Node A cached it 3 days ago, Node B just pulled a newer version.

Result: two pods running different code — some requests work, others fail randomly.

## Fix

```yaml
# Never do this in production:
image: myrepo/myapp:latest      ← different nodes = different code

# Always use an exact version:
image: myrepo/myapp:v1.2.3      ← everyone runs the same code
image: myrepo/myapp:sha-abc123  ← even better — tied to a specific Git commit
```

---

# Issue 21 — PVC Stuck in Pending

## What Is Happening?

A PVC (Persistent Volume Claim) is like asking for a storage box for your data. If you ask for a box that does not exist (wrong StorageClass) — you wait forever.

Database pods need storage. No storage = DB pod never starts = all your other services that need the DB also fail.

## How to Spot It

```bash
kubectl get pvc -n <namespace>
```

```
NAME          STATUS    STORAGECLASS   AGE
postgres-pvc  Pending   fast-ssd       10m
              ^^^^^^^   ^^^^^^^^
              ← waiting for 10 minutes
              ← StorageClass "fast-ssd" does not exist
```

## Fix

```bash
# Check what StorageClasses actually exist
kubectl get storageclass

# Delete old PVC and recreate with correct StorageClass
kubectl delete pvc postgres-pvc -n <namespace>
# Edit PVC YAML — change storageClassName to one that exists (e.g. "standard")
kubectl apply -f pvc.yaml
```

---

# Issue 22 — PV Not Released

## What Is Happening?

After you delete a PVC, the underlying storage (PV) may stay in "Released" state — not reusable. New PVCs cannot bind to it. It just sits there taking up space.

## How to Spot It

```bash
kubectl get pv
```

```
NAME        STATUS     CLAIM
pv-data-01  Released   database/postgres-pvc   ← old claim deleted but PV is stuck
```

## Fix

```bash
# Clear the old claim reference — makes PV available again
kubectl patch pv pv-data-01 \
  -p '{"spec":{"claimRef":null}}'

# Now status changes to Available and new PVCs can bind to it
```

---

# Issue 23 — Disk Full on Node

## What Is Happening?

Container logs are stored on the node. If logs are not rotated (deleted periodically), one noisy app can fill the entire disk. When the disk is full — all pods on that node get evicted.

## How to Spot It

```bash
kubectl describe node <node-name> | grep DiskPressure
```

```
DiskPressure: True    ← disk is full
```

## Fix

```bash
# Get a shell on the node to investigate
kubectl debug node/<node-name> -it --image=ubuntu

# Inside: check disk usage
df -h
du -sh /var/log/containers/* | sort -rh | head -10

# Clean up unused container images
crictl rmi --prune

# Delete old logs
find /var/log/containers -name "*.log" -mtime +7 -delete
```

---

# Issue 24 — Deployment Rollout Stuck

## What Is Happening?

When you deploy a new version, Kubernetes starts the new pod and waits for it to be healthy before removing the old one. If the new pod keeps crashing — the rollout is stuck forever. The old version keeps running (which is good) but the new version never deploys.

## How to Spot It

```bash
kubectl rollout status deployment/my-app -n <namespace>
```

```
Waiting for deployment "my-app" rollout to finish:
1 out of 2 new replicas have been updated...
← stuck here for 10+ minutes = new pod is unhealthy
```

## Fix

```bash
# Option 1 — fix the new version and redeploy
kubectl set image deployment/<name> <container>=myrepo/myapp:v1.4 -n <namespace>

# Option 2 — rollback to last working version immediately
kubectl rollout undo deployment/<name> -n <namespace>
```

---

# Issue 25 — Rollback Needed

## What Is Happening?

You deployed a new version and it is broken in production. You need to go back to the last working version immediately.

## Fix

```bash
# See all versions deployed
kubectl rollout history deployment/my-app -n <namespace>
```

```
REVISION   CHANGE-CAUSE
1          version 1.0.0    ← first deploy
2          version 1.1.0    ← this was working
3          version 2.0.0    ← current, broken
```

```bash
# Go back to revision 2
kubectl rollout undo deployment/my-app -n <namespace> --to-revision=2

# Confirm it is back
kubectl rollout status deployment/my-app -n <namespace>
# deployment "my-app" successfully rolled out
```

---

# Issue 26 — Too Many Pods, Not Enough Nodes

## What Is Happening?

You scaled up to 20 replicas but only have 4 nodes with limited resources. Extra pods go into Pending state — no room for them.

## Fix

```bash
# Check node capacity
kubectl describe nodes | grep -A5 "Allocated resources"

# Scale down to what fits
kubectl scale deployment <name> --replicas=8 -n <namespace>

# OR reduce resource requests so more pods fit per node
# OR add more nodes to the cluster
```

---

# Issue 27 — No Logs in New Relic

## What Is Happening?

The Fluent Bit log forwarder collects logs from all pods and sends them to New Relic. If the forwarder is down or using a wrong API key — no logs appear in New Relic, even though pods are running fine.

## How to Spot It

In New Relic → Logs → search: `cluster_name = 'kind-calico-prod'` → **No results**

```bash
# Check if the log forwarder pod is healthy
kubectl get pods -n newrelic | grep logging
```

```
NAME                             READY   STATUS             RESTARTS
nri-bundle-newrelic-logging-xxx  0/1     CrashLoopBackOff   8
← log forwarder is crashing = no logs going to New Relic
```

## Fix

```bash
# Check logs of the forwarder itself
kubectl logs -n newrelic -l app.kubernetes.io/name=newrelic-logging --tail=20

# If it says "401 Unauthorized" or "403 Forbidden" → wrong license key
# Update values.yaml with correct license key and re-upgrade:
helm upgrade nri-bundle newrelic/nri-bundle \
  --namespace newrelic --values values.yaml
```

---

# Issue 28 — Metrics Missing in New Relic

## What Is Happening?

Metrics (CPU, memory, pod counts) are collected by the infrastructure agent and kube-state-metrics. If these pods are unhealthy — the New Relic dashboard shows empty graphs.

## Fix

```bash
# Check all New Relic pods
kubectl get pods -n newrelic

# Check infrastructure agent logs for errors
kubectl logs -n newrelic -l app.kubernetes.io/component=kubelet --tail=20
# If "401" or "403" errors → wrong license key
```

---

# Issue 29 — Alert Storm (Too Many Alerts at Once)

## What Is Happening?

One real problem triggers dozens of alerts. For example: one node goes down → 20 pods evicted → 20 separate "Pod Not Ready" alerts fire → your phone explodes with notifications.

## Fix in New Relic

1. Go to **Alerts → Policies**
2. Change **Incident Preference** from `Per Condition` to `Per Policy`
   - This groups all related alerts into ONE incident
3. Add `min:` to thresholds so small blips don't trigger alerts
4. Use `SINCE 5 minutes ago` instead of `SINCE 1 minute ago` — reduces false alarms

---

# Issue 30 — RBAC Permission Denied

## What Is Happening?

Some apps need to talk to the Kubernetes API (e.g., monitoring agents, ArgoCD, operators). By default, pods have very limited permissions. If the app tries to list pods or read secrets — it gets **403 Forbidden**.

## How to Spot It

```bash
kubectl logs <pod-name> -n <namespace>
```

```
Error: pods is forbidden:
User "system:serviceaccount:monitoring:my-agent"
cannot list resource "pods" in API group ""
Status: 403
```

## Fix

```bash
# Create a Role that allows reading pods
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: pod-reader-binding
subjects:
- kind: ServiceAccount
  name: my-agent            ← the service account your pod uses
  namespace: monitoring
roleRef:
  kind: ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
EOF
```

---

# Quick Cheat Sheet — Which Command for Which Problem

| You see this | Run this first |
|---|---|
| `CrashLoopBackOff` | `kubectl logs <pod> --previous` |
| `OOMKilled` | `kubectl describe pod <pod>` → check Exit Code 137 |
| `ImagePullBackOff` | `kubectl describe pod <pod>` → check Events |
| `Pending` (never starts) | `kubectl describe pod <pod>` → check Events |
| `Init:0/1` | `kubectl logs <pod> -c <init-container-name>` |
| `0/1 Running` (not ready) | `kubectl describe pod <pod>` → check Readiness probe |
| `Evicted` | `kubectl describe pod <pod>` → check Message |
| Service not working | `kubectl get endpoints <service>` → is it `<none>`? |
| App slow, no errors | `kubectl top pods` → is CPU at 100% of limit? |
| HPA not scaling | `kubectl get hpa` → is TARGETS showing `<unknown>`? |
| No logs in New Relic | `kubectl get pods -n newrelic` → any pod not Running? |

---

*Last updated: April 2026 | Cluster: kind-calico-prod*
