# Kubernetes — Missing Issues (Issues 31–38)

> These are the issues NOT covered in K8s_issues.md.
> Same plain English format: What it is → Sample output → Diagnosis → Fix.

---

# Issue 31 — Resource Quota Exceeded

## What Is Happening?

A namespace can have a **budget** — a maximum amount of CPU, memory, and number of pods it is allowed to use. If you try to create a pod that would go over this budget, Kubernetes refuses to create it.

Think of it like a shared office floor with limited desks. If all desks are taken, no new employee can sit there — even if the employee is urgently needed.

## What You See (Broken)

```bash
$ kubectl apply -f payment-service.yaml
```
```
Error from server (Forbidden):
error when creating "payment-service.yaml":
pods "payment-service-xxx" is forbidden:
exceeded quota: production-quota,
requested: cpu=500m, used: cpu=9800m, limited: cpu=10000m
↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# ⚠️ PROBLEM → namespace has used 9800m of 10000m CPU limit
# ⚠️ PROBLEM → your new pod needs 500m more — total would be 10300m → rejected
```

## Diagnose

```bash
# See the quota and how much is used
$ kubectl describe resourcequota -n production
```
```
Name:     production-quota
Resource        Used    Hard
--------        ----    ----
cpu             9800m   10000m    # ⚠️ PROBLEM → 98% used, no room for new pods
memory          7Gi     8Gi       # ⚠️ PROBLEM → 87% used
pods            48      50        # ⚠️ PROBLEM → only 2 pod slots left
```

## Fix

```bash
# Option 1 — reduce requests on existing pods to free up quota
kubectl edit deployment some-service -n production
# Lower requests.cpu from 500m to 200m

# Option 2 — ask admin to raise the quota
kubectl edit resourcequota production-quota -n production
# Increase Hard limits

# Option 3 — delete unused deployments in the namespace
kubectl get deployments -n production
kubectl delete deployment old-unused-service -n production
```

## What It Looks Like When Fixed

```bash
$ kubectl describe resourcequota -n production
```
```
Resource   Used    Hard
cpu        5200m   10000m    # ✅ HEALTHY → 52% used, plenty of room
memory     4Gi     8Gi       # ✅ HEALTHY → 50% used
pods       25      50        # ✅ HEALTHY → 25 slots still available
```

---

# Issue 32 — Namespace Stuck in Terminating

## What Is Happening?

When you delete a namespace, Kubernetes needs to delete everything inside it — pods, services, secrets, etc. If any resource is waiting on something (like a finalizer that never completes), the namespace gets **stuck forever** in "Terminating" state.

Think of it like trying to check out of a hotel room but the bill keeps generating new charges — you can never leave.

## What You See (Broken)

```bash
$ kubectl get namespaces
```
```
NAME          STATUS        AGE
default       Active        72d
production    Active        30d
old-project   Terminating   45m    # ⚠️ PROBLEM → stuck for 45 minutes
                                   # 💡 MEANS  → something inside is blocking deletion
```

## Diagnose

```bash
# Check what is still inside
$ kubectl get all -n old-project
```
```
No resources found in old-project namespace.
# ⚠️ PROBLEM → namespace looks empty but still stuck
# 💡 MEANS  → a finalizer is blocking it (not visible with kubectl get all)
```

```bash
# Check for finalizers
$ kubectl get namespace old-project -o json | python3 -m json.tool | grep finalizer
```
```
"finalizers": [
    "kubernetes"    # ⚠️ PROBLEM → this finalizer is not completing
]
```

## Fix

```bash
# Remove the finalizer manually (safe to do when namespace is empty)
kubectl get namespace old-project -o json \
  | python3 -c "
import json, sys
ns = json.load(sys.stdin)
ns['spec']['finalizers'] = []
print(json.dumps(ns))
" | kubectl replace --raw /api/v1/namespaces/old-project/finalize -f -
```

## What It Looks Like When Fixed

```bash
$ kubectl get namespaces
```
```
NAME          STATUS   AGE
default       Active   72d
production    Active   30d
# old-project is gone   # ✅ HEALTHY → namespace fully deleted
```

---

# Issue 33 — CronJob Not Running

## What Is Happening?

A CronJob is a scheduled task — like a reminder on your phone that fires at a set time. If the schedule is wrong, or the previous run is still going, or the job keeps failing — it silently stops working with no obvious alert.

## What You See (Broken)

```bash
$ kubectl get cronjob -n default
```
```
NAME                    SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
payment-report          0 9 * * *     False     0        <none>          2d
                                                          ↑↑↑↑↑↑
                                                          # ⚠️ PROBLEM → "none" means it has NEVER run
                                                          # Should have run every day at 9 AM
```

## Diagnose

```bash
# Step 1 — Describe the cronjob
$ kubectl describe cronjob payment-report -n default
```
```
Schedule:   0 9 * * *
Suspend:    false
Last Schedule Time: <nil>    # ⚠️ PROBLEM → never ran

Events:
  Warning  FailedNeedsStart  5m  cronjob-controller
           Cannot determine if job needs to be started:
           too many missed start times (100).
           Set or decrease .spec.startingDeadlineSeconds.
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           # ⚠️ PROBLEM → missed too many runs (e.g. cluster was down for days)
           # Kubernetes gives up after 100 missed runs
```

```bash
# Step 2 — Check if old jobs are piling up
$ kubectl get jobs -n default | grep payment
```
```
payment-report-28501920   0/1   Failed    2d   # ⚠️ PROBLEM → old job failed
payment-report-28501921   0/1   Failed    1d   # ⚠️ PROBLEM → failed again
payment-report-28501922   0/1   Failed    23h  # ⚠️ PROBLEM → pattern of failure
# concurrencyPolicy: Forbid → new job won't start while old failed job exists
```

```bash
# Step 3 — Read the failed job logs
$ kubectl logs job/payment-report-28501920 -n default
```
```
Error: cannot connect to reporting database
connection refused: report-db:5432    # ⚠️ ROOT CAUSE → reporting DB is down
```

## Fix

```bash
# Delete failed old jobs so new one can start
kubectl delete jobs -n default -l job-name=payment-report

# Fix the DB connection issue, then manually trigger a run
kubectl create job payment-report-manual \
  --from=cronjob/payment-report -n default
```

## What It Looks Like When Fixed

```bash
$ kubectl get cronjob -n default
```
```
NAME              SCHEDULE    ACTIVE   LAST SCHEDULE   AGE
payment-report    0 9 * * *   0        2m ago          2d    # ✅ HEALTHY → ran 2 minutes ago
```

---

# Issue 34 — StatefulSet Pod Stuck (Ordered Start)

## What Is Happening?

StatefulSets are used for apps that need to keep their identity — like databases. They start pods **in strict order**: pod-0 must be healthy before pod-1 starts. If pod-0 is stuck, pod-1 and pod-2 will never start — they just wait forever.

## What You See (Broken)

```bash
$ kubectl get pods -n database
```
```
NAME            READY   STATUS             RESTARTS   AGE
postgres-0      0/1     CrashLoopBackOff   8          20m   # ⚠️ PROBLEM → pod-0 crashing
postgres-1      0/1     Pending            0          20m   # ⚠️ PROBLEM → waiting for pod-0
postgres-2      0/1     Pending            0          20m   # ⚠️ PROBLEM → waiting for pod-1
                        ↑↑↑↑↑↑↑
                        # All pods after index 0 are stuck in Pending
                        # They will NEVER start until pod-0 is healthy
```

## Diagnose

```bash
# Focus on pod-0 first — it is always the blocker
$ kubectl logs postgres-0 -n database --previous
```
```
FATAL: data directory "/var/lib/postgresql/data" has wrong ownership
       data dir permissions must be 0700
       ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
       # ⚠️ ROOT CAUSE → volume mounted with wrong permissions
       # Fix pod-0 first, all others will follow
```

## Fix

```bash
# Fix the volume permissions issue in the StatefulSet
kubectl edit statefulset postgres -n database
# Add initContainer to fix permissions:
# initContainers:
# - name: fix-permissions
#   image: busybox
#   command: ["chown", "-R", "999:999", "/var/lib/postgresql/data"]

# Delete the stuck pod-0 (StatefulSet will recreate it)
kubectl delete pod postgres-0 -n database

# Watch pods come up in order (0 → 1 → 2)
kubectl get pods -n database -w
```

## What It Looks Like When Fixed

```bash
$ kubectl get pods -n database
```
```
NAME          READY   STATUS    RESTARTS   AGE
postgres-0    1/1     Running   0          5m    # ✅ pod-0 healthy first
postgres-1    1/1     Running   0          4m    # ✅ pod-1 starts after pod-0
postgres-2    1/1     Running   0          3m    # ✅ pod-2 starts after pod-1
```

---

# Issue 35 — Admission Webhook Blocking Pod Creation

## What Is Happening?

Admission webhooks are like security checkpoints — every new pod passes through them before being created. If the webhook itself is down or misconfigured, it rejects **all** new pods, including completely correct ones.

Think of it like airport security — if the scanner breaks, no one boards the plane, even if they have a valid ticket.

## What You See (Broken)

```bash
$ kubectl apply -f my-deployment.yaml
```
```
Error from server (InternalError):
error when creating "my-deployment.yaml":
Internal error occurred:
failed calling webhook "validate.newrelic.com":
failed to call webhook:
Post "https://nri-bundle-nri-metadata-injection.newrelic.svc:443/mutate":
dial tcp 10.96.21.167:443: connect: connection refused
↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# ⚠️ PROBLEM → the webhook pod is down
# ⚠️ PROBLEM → ALL new pods are rejected until this is fixed
```

## Diagnose

```bash
# Find the webhook pod
$ kubectl get pods -n newrelic | grep metadata
```
```
nri-bundle-nri-metadata-injection-xxx   0/1   CrashLoopBackOff   5   10m
                                               ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                                               # ⚠️ PROBLEM → webhook is down = everything blocked
```

```bash
# List all webhooks
$ kubectl get mutatingwebhookconfigurations
```
```
NAME                                  WEBHOOKS   AGE
nri-bundle-nri-metadata-injection     1          5d    # ← this is the problematic one
```

## Fix

```bash
# Option 1 — Fix the webhook pod
kubectl rollout restart deployment nri-bundle-nri-metadata-injection -n newrelic

# Option 2 — If webhook is not critical, delete it temporarily
kubectl delete mutatingwebhookconfiguration nri-bundle-nri-metadata-injection
# Pods will now create successfully
# Reinstall the webhook after fixing the underlying issue
```

---

# Issue 36 — Requests Dropped During Deployment (Graceful Shutdown)

## What Is Happening?

When you deploy a new version, Kubernetes terminates old pods. If a pod is killed while it is in the middle of handling a request — that request fails with a connection error.

Think of it like cutting the phone line while someone is mid-call. The person on the other end gets silence.

## What You See (Broken)

```
During rolling deployment:
  Error rate spikes for 10-30 seconds
  Logs show: "connection reset by peer"
  Users get intermittent 502 errors
  After deployment finishes: everything is fine again
  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
  # ⚠️ PROBLEM → requests dropped during pod termination
  # 💡 MEANS  → pod killed before finishing active requests
```

## Diagnose

```bash
# Check if pod has a preStop hook configured
$ kubectl describe pod my-app-xxx -n production
```
```
Lifecycle:
  PreStop:  <nil>    # ⚠️ PROBLEM → no preStop hook = pod dies immediately on kill signal

Termination Grace Period: 30s   # 30s is given but pod ignores it without preStop hook
```

## Fix

```yaml
# Add preStop hook — gives pod time to finish active requests before dying
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
      # 💡 This tells pod: wait 15 seconds before starting shutdown
      # In those 15 seconds: finish active requests, stop accepting new ones

# Also set terminationGracePeriodSeconds
terminationGracePeriodSeconds: 60   # total time Kubernetes waits before force-killing
```

---

# Issue 37 — Sidecar Container Failing

## What Is Happening?

Some pods have a helper container (sidecar) running alongside the main app — for logging, security, service mesh (Istio/Envoy), etc. If the sidecar crashes, Kubernetes restarts the **whole pod**, including the healthy main app.

## What You See (Broken)

```bash
$ kubectl get pods -n production
```
```
NAME                READY   STATUS             RESTARTS   AGE
payment-app-xxx     1/2     CrashLoopBackOff   12         30m
                    ↑↑↑
                    # ⚠️ PROBLEM → 1 out of 2 containers running
                    # 💡 MEANS  → one container is fine, one is crashing (the sidecar)
```

## Diagnose

```bash
# Step 1 — See which container is crashing
$ kubectl describe pod payment-app-xxx -n production
```
```
Containers:
  payment-app:           # main app
    State: Running       # ✅ main app is healthy
    Ready: True

  envoy-proxy:           # sidecar (service mesh)
    State: CrashLoopBackOff   # ⚠️ PROBLEM → sidecar is crashing
    Ready: False
    Restart Count: 12
```

```bash
# Step 2 — Read the sidecar logs specifically
$ kubectl logs payment-app-xxx -n production -c envoy-proxy --previous
```
```
[error] failed to fetch config from control plane
        connection refused: istio-pilot.istio-system.svc:15010
        ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ⚠️ ROOT CAUSE → Istio control plane is down
        # Envoy sidecar cannot get its config → crashes
```

## Fix

```bash
# Fix the control plane (Istio pilot in this case)
kubectl get pods -n istio-system
kubectl rollout restart deployment istiod -n istio-system

# Once control plane is back, the sidecar will recover
```

---

# Issue 38 — ConfigMap Change Not Picked Up by Running Pod

## What Is Happening?

When you update a ConfigMap, pods that loaded it as **environment variables** do NOT automatically see the new values. The old values are baked in at startup and stay until the pod restarts.

Think of it like changing a recipe book — the chef already memorized the old recipe. You need to call the chef back in (restart the pod) to learn the new recipe.

## What You See (Broken)

```bash
# You updated the ConfigMap
$ kubectl edit configmap app-config -n production
# Changed: LOG_LEVEL from "info" to "debug"

# But running pods still see the OLD value
$ kubectl exec my-app-xxx -n production -- env | grep LOG_LEVEL
```
```
LOG_LEVEL=info    # ⚠️ PROBLEM → still showing old value "info" not "debug"
                  # 💡 MEANS  → env vars from ConfigMap are set at pod START time
                  # 💡 MEANS  → pod must restart to pick up new values
```

## Fix

```bash
# Restart all pods in the deployment to pick up new ConfigMap values
kubectl rollout restart deployment my-app -n production

# Verify after restart
kubectl exec my-app-xxx -n production -- env | grep LOG_LEVEL
# LOG_LEVEL=debug   ✅ new value now loaded
```

> **Note:** If ConfigMap is mounted as a **file** (not env var), it updates automatically within ~60 seconds — no restart needed. Only env vars require a pod restart.

---

# Quick Reference — Issues 31–38

| Issue | How to Spot | First Command |
|---|---|---|
| Resource Quota Exceeded | `kubectl apply` returns Forbidden | `kubectl describe resourcequota -n <ns>` |
| Namespace Terminating | `kubectl get ns` shows Terminating forever | `kubectl get namespace <ns> -o json` |
| CronJob Not Running | LAST SCHEDULE shows `<none>` | `kubectl describe cronjob <name>` |
| StatefulSet Stuck | pod-1 and pod-2 in Pending, pod-0 failing | `kubectl logs <statefulset>-0 --previous` |
| Webhook Blocking | `kubectl apply` returns Internal Error | `kubectl get pods -n <webhook-namespace>` |
| Requests Dropped | 502 spikes only during deployments | `kubectl describe pod` → check Lifecycle |
| Sidecar Failing | `1/2` or `0/2` in READY column | `kubectl logs <pod> -c <sidecar-name>` |
| ConfigMap Not Reloading | env var shows old value after CM update | `kubectl rollout restart deployment <name>` |
