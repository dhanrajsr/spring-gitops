# Kubernetes Issues — Diagnosis & Fix Playbook

A practical reference for diagnosing and resolving the most common Kubernetes issues in production.

---

## Universal First Steps — Always Start Here

Every time something is wrong, run these 3 commands first:

```bash
# Step 1 — Get the big picture (find all non-running pods)
kubectl get pods -A | grep -v Running | grep -v Completed

# Step 2 — Find the root cause
kubectl describe pod <pod-name> -n <namespace>

# Step 3 — Read the logs
kubectl logs <pod-name> -n <namespace> --previous
```

---

## Quick Reference — Diagnosis Decision Tree

```
Pod not working?
│
├── kubectl get pods → what STATUS?
│
├── CrashLoopBackOff ──► kubectl logs --previous + describe (exit code)
├── OOMKilled        ──► kubectl top pod + increase memory limit
├── ImagePullBackOff ──► describe → check image name + registry secret
├── Pending          ──► describe → node capacity or selector mismatch
├── Init:0/1         ──► kubectl logs -c <init-container-name>
│
├── Running but app fails?
│   ├── kubectl get endpoints <svc> → empty = label mismatch
│   ├── kubectl run test-pod → curl service → DNS issue?
│   └── kubectl top pod → at CPU limit = throttling
│
└── In New Relic:
    ├── Infrastructure → Kubernetes → check red pods
    ├── APM → high response time = slow endpoint or throttling
    ├── Logs → filter level=error → find stack trace
    └── Alerts → Issues → which condition fired + which pod
```

---

# Category 1 — Pod Failures

---

## Issue 1 — CrashLoopBackOff

**What it means:** Pod starts, crashes, Kubernetes restarts it, crashes again.
Backoff timer grows: 10s → 20s → 40s → 5min.

### Diagnose

```bash
# Step 1 — Confirm
kubectl get pods -n <namespace>
# NAME                    READY   STATUS             RESTARTS
# my-app-xxx              0/1     CrashLoopBackOff   6

# Step 2 — Check exit code (tells you WHY it crashed)
kubectl describe pod <pod-name> -n <namespace>
# Look for:
#   Last State: Terminated
#   Exit Code: 1    ← app error
#   Exit Code: 137  ← OOMKilled (memory exceeded)
#   Exit Code: 139  ← Segfault

# Step 3 — Read crash logs from PREVIOUS run (not current)
kubectl logs <pod-name> -n <namespace> --previous

# Step 4 — Check Kubernetes events
kubectl describe pod <pod-name> -n <namespace> | grep -A20 Events
```

### In New Relic
> Infrastructure → Kubernetes → Pods → click the pod → check Exit Code + View logs

### Fix by Exit Code

| Exit Code | Cause | Fix |
|---|---|---|
| 1 | App error at startup | Check logs — missing env var, DB unreachable |
| 137 | OOMKilled | Increase memory limit |
| 139 | Segfault | Bug in app or wrong base image |

```yaml
# Fix — increase memory limit in deployment
resources:
  requests:
    memory: "256Mi"
  limits:
    memory: "512Mi"   # increase this
```

```bash
# Restart after fix
kubectl rollout restart deployment <name> -n <namespace>
```

---

## Issue 2 — OOMKilled

**What it means:** App used more memory than its limit. Kubernetes killed it silently.
Pod shows Running → suddenly gone → CrashLoopBackOff.

### Diagnose

```bash
# Step 1 — Check reason (OOMKilled)
kubectl describe pod <pod-name> -n <namespace>
# Last State: Terminated
# Reason:     OOMKilled
# Exit Code:  137

# Step 2 — Check current memory usage
kubectl top pod <pod-name> -n <namespace>
# NAME     CPU   MEMORY
# my-app   10m   480Mi   ← close to or over limit

# Step 3 — Check what the limit is set to
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.spec.containers[0].resources}'
```

### In New Relic
> Dashboards → kind-calico-prod → Traffic & Chaos → "Memory Pressure" widget
> Look for: memory spike → sudden drop to 0 = OOMKill moment

### Fix

```bash
# Option 1 — increase memory limit via kubectl
kubectl set resources deployment <name> -n <namespace> \
  --limits=memory=1Gi --requests=memory=512Mi

# Option 2 — edit deployment YAML
kubectl edit deployment <name> -n <namespace>
# Update: limits.memory: 1Gi

# Option 3 — find memory leak via APM
# APM → Transactions → find endpoint that causes memory spike
```

---

## Issue 3 — ImagePullBackOff

**What it means:** Kubernetes cannot pull the container image from the registry.

### Diagnose

```bash
# Step 1 — Confirm
kubectl get pods -n <namespace>
# NAME      READY   STATUS             RESTARTS
# my-app    0/1     ImagePullBackOff   0

# Step 2 — Find the exact error
kubectl describe pod <pod-name> -n <namespace>
# Events:
#   Failed to pull image "myrepo/myapp:v1.2":
#   unauthorized: authentication required  ← missing registry secret
#   not found                              ← wrong image name or tag

# Step 3 — Test manually
docker pull myrepo/myapp:v1.2
```

### Fix

```bash
# Fix 1 — Wrong image name or tag
kubectl set image deployment/<name> <container>=myrepo/myapp:v1.3 -n <namespace>

# Fix 2 — Private registry — create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=myrepo.example.com \
  --docker-username=myuser \
  --docker-password=mypassword \
  -n <namespace>

# Attach secret to deployment
kubectl patch deployment <name> -n <namespace> \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"regcred"}]}}}}'
```

---

## Issue 4 — Pod Stuck in Pending

**What it means:** Pod was created but no node could schedule it.

### Diagnose

```bash
# Step 1 — Confirm pending
kubectl get pods -n <namespace>
# NAME      READY   STATUS    RESTARTS
# my-app    0/1     Pending   0

# Step 2 — THIS is the key command for Pending pods
kubectl describe pod <pod-name> -n <namespace>
# Events:
#   0/4 nodes are available:
#   4 Insufficient memory       ← nodes full
#   4 Insufficient cpu          ← nodes full
#   4 node(s) didn't match node selector  ← wrong label

# Step 3 — Check node capacity
kubectl describe nodes | grep -A5 "Allocated resources"
# If cpu: 95%, memory: 89% → nodes are full

# Step 4 — Check pod resource requests
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.spec.containers[0].resources}'
```

### Fix

```bash
# Fix 1 — Nodes full, reduce requests
kubectl edit deployment <name> -n <namespace>
# Lower: requests.cpu and requests.memory

# Fix 2 — Wrong node selector, check available labels
kubectl get nodes --show-labels
# Update deployment nodeSelector to match actual node labels

# Fix 3 — Add more nodes (cloud)
# EKS: increase node group desired capacity
# Kind: add more worker nodes
```

---

## Issue 5 — Init Container Failing

**What it means:** Init container runs before the main app. If it fails, main app never starts.

### Diagnose

```bash
# Step 1 — Spot it
kubectl get pods -n <namespace>
# NAME      READY   STATUS     RESTARTS
# my-app    0/1     Init:0/1   0

# Step 2 — Find the init container name
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Init Containers"

# Step 3 — Check init container logs specifically
kubectl logs <pod-name> -n <namespace> -c <init-container-name>
```

### Common Causes & Fixes

```bash
# Cause 1 — Waiting for DB that's not ready
# Check if DB is running first
kubectl get pods -n <namespace> | grep db
kubectl logs <db-pod> -n <namespace>

# Cause 2 — Script error (missing command, wrong path)
# Check the init container command in describe output

# Cause 3 — Wrong volume mount permissions
kubectl exec <pod-name> -n <namespace> -c <init-container> -- ls -la /mount/path
```

---

# Category 2 — Networking Issues

---

## Issue 6 — Service Not Reachable

**What it means:** App is running but requests fail with "Connection refused" or timeout.

### Diagnose

```bash
# Step 1 — Check if service exists
kubectl get svc -n <namespace>

# Step 2 — Check endpoints (THIS is the most important check)
kubectl get endpoints <service-name> -n <namespace>
# If output: <none>  ← NO pods match the selector = root cause

# Step 3 — Compare service selector vs pod labels
kubectl describe svc <service-name> -n <namespace>
# Selector: app=myapp   ← service expects this label

kubectl get pods -n <namespace> --show-labels
# Check if any pod actually has: app=myapp

# Step 4 — Test connectivity from inside cluster
kubectl run test-pod --image=curlimages/curl -it --rm -- \
  curl http://<service-name>.<namespace>.svc.cluster.local
```

### Fix

```bash
# Fix mismatched label — update service selector
kubectl patch svc <service-name> -n <namespace> \
  -p '{"spec":{"selector":{"app":"correct-label-value"}}}'

# Or fix the pod labels to match the service
kubectl label pod <pod-name> -n <namespace> app=myapp
```

---

## Issue 7 — DNS Resolution Failure

**What it means:** App says "could not resolve host". DNS inside the cluster is broken.

### Diagnose

```bash
# Step 1 — Test DNS from inside a pod
kubectl run dns-test --image=busybox --rm -it -- \
  nslookup kubernetes.default.svc.cluster.local
# If this fails — CoreDNS is broken

# Step 2 — Check CoreDNS pods
kubectl get pods -n kube-system | grep coredns
# Should be Running

# Step 3 — Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns

# Step 4 — Verify correct DNS format
# Format:  <service>.<namespace>.svc.cluster.local
# Wrong:   frontend-svc                          ← only works in same namespace
# Correct: frontend-svc.frontend.svc.cluster.local  ← cross-namespace
```

### Fix

```bash
# Fix 1 — CoreDNS crashing, restart it
kubectl rollout restart deployment coredns -n kube-system

# Fix 2 — App using wrong hostname
kubectl set env deployment/<app> -n <namespace> \
  DB_HOST=postgres-svc.database.svc.cluster.local
```

---

## Issue 8 — Ingress Not Routing (404 / 502)

**What it means:** Browser hits the URL, gets 404 or 502. Traffic is not reaching the pod.

### Diagnose

```bash
# Step 1 — Check ingress exists and has an address
kubectl get ingress -n <namespace>
# ADDRESS column must have an IP — if empty, controller not working

# Step 2 — Check ingress rules
kubectl describe ingress <ingress-name> -n <namespace>
# Rules: host=myapp.example.com → service:myapp-svc:80
# Verify service name and port are correct

# Step 3 — Check ingress controller is running
kubectl get pods -n ingress-nginx

# Step 4 — Check ingress controller logs
kubectl logs -n ingress-nginx \
  -l app.kubernetes.io/name=ingress-nginx --tail=50
# "upstream not found" → wrong backend service
# "no backend"         → service has no endpoints

# Step 5 — Test backend service directly (bypass ingress)
kubectl port-forward svc/<service-name> 8080:80 -n <namespace>
curl http://localhost:8080
```

### Fix by Symptom

| Symptom | Fix |
|---|---|
| 404 from browser | Wrong `path` or `host` in Ingress spec |
| 502 Bad Gateway | Backend pod crashing or wrong `targetPort` |
| No ADDRESS on ingress | Ingress controller not installed or not running |

---

## Issue 9 — Network Policy Blocking Traffic

**What it means:** Traffic is blocked between pods due to Calico/NetworkPolicy rules.

### Diagnose

```bash
# Step 1 — Check if NetworkPolicies exist
kubectl get networkpolicies -A

# Step 2 — Test connectivity between pods
kubectl exec <source-pod> -n <namespace> -- \
  curl -v http://<target-service>.<target-namespace>.svc.cluster.local

# Step 3 — Check policy rules
kubectl describe networkpolicy <policy-name> -n <namespace>
# Look at: PodSelector, PolicyTypes, Ingress/Egress rules
```

### Fix

```bash
# Allow traffic between two namespaces
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: backend
spec:
  podSelector: {}
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: frontend
EOF
```

---

## Issue 10 — LoadBalancer EXTERNAL-IP Pending

**What it means:** Service type LoadBalancer never gets an external IP.

### Diagnose

```bash
kubectl get svc -n <namespace>
# NAME       TYPE           CLUSTER-IP   EXTERNAL-IP   PORT(S)
# my-svc     LoadBalancer   10.96.1.1    <pending>     80:30080/TCP

# This is expected on: Kind, Minikube, bare metal
# On Kind — use NodePort or port-forward instead
kubectl port-forward svc/<service-name> 8080:80 -n <namespace>
```

### Fix

```bash
# Fix for Kind/bare metal — install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.5/config/manifests/metallb-native.yaml

# Or change service type to NodePort
kubectl patch svc <service-name> -n <namespace> \
  -p '{"spec":{"type":"NodePort"}}'
```

---

# Category 3 — Resource Issues

---

## Issue 11 — Node NotReady

**What it means:** A node has gone offline. All pods on it are evicted or stuck.

### Diagnose

```bash
# Step 1 — Identify NotReady node
kubectl get nodes
# NAME              STATUS     ROLES    AGE
# calico-worker2    NotReady   <none>   5d

# Step 2 — Check node conditions
kubectl describe node <node-name>
# Conditions:
#   DiskPressure:    True  ← disk full
#   MemoryPressure:  True  ← RAM full
#   PIDPressure:     True  ← too many processes
#   Ready:           False

# Step 3 — Check kubelet status on the node
# (if you have SSH access to the node)
systemctl status kubelet
journalctl -u kubelet -n 50
```

### Fix

```bash
# Fix disk pressure — clean up old images and logs
kubectl debug node/<node-name> -it --image=ubuntu -- bash
# Inside: df -h, du -sh /var/log/*, docker system prune

# Cordon node (stop new pods scheduling on it)
kubectl cordon <node-name>

# Drain node (move all pods off safely)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# After fix, uncordon
kubectl uncordon <node-name>
```

---

## Issue 12 — Evicted Pods

**What it means:** Kubernetes forcibly removed pods because a node ran out of resources.

### Diagnose

```bash
# Step 1 — Find evicted pods
kubectl get pods -A | grep Evicted

# Step 2 — Check reason for eviction
kubectl describe pod <evicted-pod> -n <namespace>
# Message: The node was low on resource: memory
#          Threshold quantity: 100Mi, available: 50Mi

# Step 3 — Check node pressure
kubectl describe node <node-name> | grep -A5 Conditions
```

### Fix

```bash
# Clean up evicted pods
kubectl get pods -A | grep Evicted | \
  awk '{print "kubectl delete pod " $2 " -n " $1}' | bash

# Fix root cause — set resource limits on all deployments
# Set requests and limits to prevent one pod from consuming all resources
```

---

## Issue 13 — CPU Throttling (App Slow, No Alerts)

**This is the most silent killer.** Pod is Running, no errors, but app is slow.

### Diagnose

```bash
# Step 1 — Check CPU usage vs limit
kubectl top pods -n <namespace>
# NAME     CPU    MEMORY
# my-app   498m   200Mi  ← almost at 500m limit = throttled

# Step 2 — Check what the limit is
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.spec.containers[0].resources.limits}'
```

### In New Relic
> APM → Transactions → high response time + 0% error rate = throttling signature
> Dashboards → Traffic & Chaos → CPU Spike Detection → line is flat at limit

### Fix

```yaml
# Increase or remove CPU limit
resources:
  requests:
    cpu: "200m"
  limits:
    cpu: "1000m"   # increase from 500m
```

---

## Issue 14 — No Resource Limits Set

**What it means:** One runaway pod can starve all others on the node.

### Diagnose

```bash
# Find all pods without limits
kubectl get pods -A -o json | \
  python3 -c "
import json,sys
pods=json.load(sys.stdin)
for p in pods['items']:
  for c in p['spec']['containers']:
    if not c.get('resources',{}).get('limits'):
      print(p['metadata']['namespace'], p['metadata']['name'], c['name'])
"
```

### Fix

```yaml
# Always set both requests and limits
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

---

## Issue 15 — HPA Not Scaling

**What it means:** HPA is configured but pods don't scale under load.

### Diagnose

```bash
# Step 1 — Check HPA status
kubectl get hpa -n <namespace>
# NAME    REFERENCE       TARGETS         MINPODS  MAXPODS  REPLICAS
# my-hpa  Deployment/app  <unknown>/70%   2        10       2
# <unknown> = metrics server can't get data

# Step 2 — Check if metrics server is running
kubectl get pods -n kube-system | grep metrics-server

# Step 3 — Test metrics directly
kubectl top pods -n <namespace>
# If this fails — metrics server is the problem

# Step 4 — Check HPA events
kubectl describe hpa <hpa-name> -n <namespace>
# "failed to get cpu utilization" ← metrics server issue
```

### Fix

```bash
# Install metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For Kind/kubeadm — add --kubelet-insecure-tls flag
kubectl patch deployment metrics-server -n kube-system \
  --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

# Category 4 — Configuration Errors

---

## Issue 16 — Missing Secret / ConfigMap

### Diagnose

```bash
# Pod will show: CreateContainerConfigError or CrashLoopBackOff
kubectl describe pod <pod-name> -n <namespace>
# Events:
#   Error: secret "my-secret" not found
#   Error: couldn't find key DB_PASSWORD in Secret

# Check what exists
kubectl get secrets -n <namespace>
kubectl get configmaps -n <namespace>
```

### Fix

```bash
# Create missing secret
kubectl create secret generic my-secret \
  --from-literal=DB_PASSWORD=mypassword \
  --from-literal=DB_USER=admin \
  -n <namespace>

# Restart pods to pick up the new secret
kubectl rollout restart deployment <name> -n <namespace>
```

---

## Issue 17 — Wrong Environment Variable

### Diagnose

```bash
# Check what env vars are actually set in the running pod
kubectl exec <pod-name> -n <namespace> -- env | grep DB_

# Compare with what's defined in the deployment
kubectl describe deployment <name> -n <namespace> | grep -A5 Environment
```

### Fix

```bash
# Update the env var
kubectl set env deployment/<name> -n <namespace> \
  DB_HOST=postgres-svc.database.svc.cluster.local

# Rollout restart to apply
kubectl rollout restart deployment <name> -n <namespace>
```

---

## Issue 18 — Liveness Probe Failing

**What it means:** Pod keeps restarting every few minutes — probe says it's dead.

### Diagnose

```bash
# Events will show probe failures
kubectl describe pod <pod-name> -n <namespace>
# Liveness probe failed: HTTP probe failed with statuscode: 404

# Test the probe endpoint manually from inside the pod
kubectl exec <pod-name> -n <namespace> -- \
  curl -s http://localhost:8080/health
# If 404 — wrong path in probe config
```

### Fix

```yaml
livenessProbe:
  httpGet:
    path: /health        # must exist in your app
    port: 8080
  initialDelaySeconds: 30  # give app time to start before first probe
  periodSeconds: 10
  failureThreshold: 3
```

---

## Issue 19 — Readiness Probe Failing

**What it means:** Pod runs but never receives traffic — readiness keeps failing.

### Diagnose

```bash
kubectl describe pod <pod-name> -n <namespace>
# Readiness probe failed: connection refused
# → app hasn't started yet but probe fires too early

kubectl get pod <pod-name> -n <namespace>
# READY column shows 0/1 — pod excluded from service endpoints
```

### Fix

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 15    # wait before first check
  periodSeconds: 5
  failureThreshold: 6        # allow more failures before excluding
```

---

## Issue 20 — Wrong Image Tag (`:latest`)

**What it means:** Different nodes have different cached versions of `latest`. Inconsistent behavior.

### Fix

```yaml
# Never use :latest in production
image: myrepo/myapp:latest    # BAD

# Always use a specific tag
image: myrepo/myapp:v1.2.3    # GOOD
image: myrepo/myapp:sha-abc123 # BEST (immutable)
```

---

# Category 5 — Storage Issues

---

## Issue 21 — PVC Stuck in Pending

### Diagnose

```bash
# Step 1 — Check PVC status
kubectl get pvc -n <namespace>
# NAME     STATUS    VOLUME   CAPACITY   STORAGECLASS
# my-pvc   Pending                       fast-ssd     ← wrong StorageClass

# Step 2 — Describe shows why
kubectl describe pvc <pvc-name> -n <namespace>
# Events:
#   no persistent volumes available for this claim
#   storageclass "fast-ssd" not found

# Step 3 — Check available StorageClasses
kubectl get storageclass
```

### Fix

```bash
# Use an existing StorageClass
kubectl patch pvc <pvc-name> -n <namespace> \
  -p '{"spec":{"storageClassName":"standard"}}'

# Or delete and recreate with correct StorageClass
kubectl delete pvc <pvc-name> -n <namespace>
# Edit YAML — change storageClassName to match available one
kubectl apply -f pvc.yaml
```

---

## Issue 22 — PV Not Released

### Diagnose

```bash
kubectl get pv
# NAME     CAPACITY  STATUS     CLAIM
# my-pv    10Gi      Released   ← not reusable — reclaim policy is Retain
```

### Fix

```bash
# Manually release the PV by removing the claimRef
kubectl patch pv <pv-name> \
  -p '{"spec":{"claimRef":null}}'
# Status changes: Released → Available
```

---

## Issue 23 — Disk Full on Node

### Diagnose

```bash
# Check node disk pressure
kubectl describe node <node-name> | grep DiskPressure
# DiskPressure: True

# SSH into node and check
df -h
du -sh /var/log/containers/*  | sort -rh | head -10
```

### Fix

```bash
# Clean up unused docker images and containers
crictl rmi --prune
# Or
docker system prune -f

# Delete old logs
find /var/log/containers -name "*.log" -mtime +7 -delete
```

---

# Category 6 — Deployment & Rollout

---

## Issue 24 — Deployment Stuck (Rollout Not Completing)

### Diagnose

```bash
# Step 1 — Check rollout status
kubectl rollout status deployment/<name> -n <namespace>
# Waiting for deployment "my-app" rollout to finish: 1 out of 2 new replicas...

# Step 2 — Check why new pod is not ready
kubectl get pods -n <namespace>
# New pod is CrashLoopBackOff or ImagePullBackOff

# Step 3 — Check deployment events
kubectl describe deployment <name> -n <namespace>
```

### Fix

```bash
# Option 1 — fix the issue in the new image, redeploy
kubectl set image deployment/<name> <container>=myrepo/myapp:v1.4 -n <namespace>

# Option 2 — rollback to previous working version
kubectl rollout undo deployment/<name> -n <namespace>

# Verify rollback
kubectl rollout status deployment/<name> -n <namespace>
```

---

## Issue 25 — Rollback Needed

### Fix

```bash
# Check rollout history
kubectl rollout history deployment/<name> -n <namespace>

# Rollback to previous version
kubectl rollout undo deployment/<name> -n <namespace>

# Rollback to specific revision
kubectl rollout undo deployment/<name> -n <namespace> --to-revision=3
```

---

# Category 7 — Observability Issues

---

## Issue 27 — No Logs in New Relic

### Diagnose

```bash
# Check if log forwarder is running
kubectl get pods -n newrelic | grep logging
# nri-bundle-newrelic-logging-xxx   1/1   Running

# Check Fluent Bit logs
kubectl logs -n newrelic -l app.kubernetes.io/name=newrelic-logging --tail=30
# Look for: "authentication failed" or "connection refused"
```

### Fix

```bash
# Verify license key is correct
kubectl get secret nri-bundle-newrelic-logging-config -n newrelic \
  -o jsonpath='{.data.LICENSE_KEY}' | base64 -d

# Reinstall with correct key
helm upgrade nri-bundle newrelic/nri-bundle \
  --namespace newrelic \
  --values values.yaml
```

---

## Issue 28 — Metrics Missing in New Relic

### Diagnose

```bash
# Check Prometheus scraper
kubectl get pods -n newrelic | grep prometheus
kubectl logs -n newrelic -l app.kubernetes.io/name=nri-prometheus --tail=30

# Check if kube-state-metrics is running
kubectl get pods -n newrelic | grep kube-state
```

---

## Issue 30 — RBAC Permission Denied

**What it means:** Pod tries to call the Kubernetes API but gets 403 Forbidden.

### Diagnose

```bash
# Check pod logs for RBAC error
kubectl logs <pod-name> -n <namespace>
# Error: pods is forbidden: User "system:serviceaccount:default:my-sa"
#        cannot list resource "pods"

# Check what ServiceAccount the pod uses
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.spec.serviceAccountName}'

# Check existing ClusterRoleBindings for that SA
kubectl get clusterrolebindings -o wide | grep <service-account-name>
```

### Fix

```bash
# Create ClusterRole and bind it to the ServiceAccount
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods", "services", "endpoints"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: pod-reader-binding
subjects:
- kind: ServiceAccount
  name: my-sa
  namespace: default
roleRef:
  kind: ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
EOF
```

---

## New Relic — Observability Workflow

```
Alert fires in New Relic
        │
        ▼
1. Alerts → Issues & Activity
   └─ Which condition? Which pod/node?
        │
        ▼
2. Infrastructure → Kubernetes → kind-calico-prod
   └─ Pods tab → find the red pod
   └─ Click pod → Exit Code? Restart Count? View Logs?
        │
        ▼
3. APM → Services
   └─ Error rate spike? Response time high?
   └─ Transactions → find the slow/failing endpoint
   └─ Distributed Tracing → trace the full request path
        │
        ▼
4. Logs → search cluster_name = 'kind-calico-prod'
   └─ Filter: level = error
   └─ Correlate timestamp with the alert
        │
        ▼
5. kubectl to confirm and fix
   └─ describe pod → find root cause
   └─ logs --previous → read crash output
   └─ rollout restart / rollout undo
```

---

*Last updated: April 2026 | Cluster: kind-calico-prod*
