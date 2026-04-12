# Kubernetes Production Troubleshooting Guide
> **Audience:** Intermediate–Advanced DevOps / SRE Engineers  
> **Scope:** Production-grade cloud-native environments (AWS EKS, GCP GKE, Azure AKS, on-prem)  
> **Philosophy:** Diagnose systematically — events → logs → metrics → network → storage

---

## Table of Contents

1. [Pod CrashLoopBackOff](#1-pod-crashloopbackoff)
2. [ImagePullBackOff / ErrImagePull](#2-imagepullbackoff--errimagepull)
3. [OOMKilled (Out of Memory)](#3-oomkilled-out-of-memory)
4. [Pending Pods — Scheduling Failures](#4-pending-pods--scheduling-failures)
5. [DNS Resolution Failures](#5-dns-resolution-failures)
6. [Service Not Reachable / Connectivity Issues](#6-service-not-reachable--connectivity-issues)
7. [Node Pressure (Memory / Disk / PID)](#7-node-pressure-memory--disk--pid)
8. [PersistentVolume / PVC Issues](#8-persistentvolume--pvc-issues)
9. [Evicted Pods](#9-evicted-pods)
10. [RBAC / Unauthorized Access Errors](#10-rbac--unauthorized-access-errors)
11. [HorizontalPodAutoscaler (HPA) Not Scaling](#11-horizontalpodautoscaler-hpa-not-scaling)
12. [Ingress / TLS Misconfiguration](#12-ingress--tls-misconfiguration)
13. [etcd Performance / Data Issues](#13-etcd-performance--data-issues)
14. [ConfigMap / Secret Misconfiguration](#14-configmap--secret-misconfiguration)
15. [Init Container Failures](#15-init-container-failures)
16. [Cluster Autoscaler Failures](#16-cluster-autoscaler-failures)
17. [Zombie / Terminating Namespaces and Resources](#17-zombie--terminating-namespaces-and-resources)

---

## Debugging Mental Model

Before diving into individual issues, internalize this first-response checklist:

```
1. kubectl get pods -n <ns>            → What is the current state?
2. kubectl describe pod <pod> -n <ns>  → Events, conditions, resource requests
3. kubectl logs <pod> -n <ns>          → App-level errors
4. kubectl logs <pod> --previous       → Logs from the last crash
5. kubectl get events -n <ns> --sort-by='.lastTimestamp'  → Cluster-level events
6. kubectl top nodes / kubectl top pods → Resource pressure
7. Check node conditions              → kubectl describe node <node>
```

> **Golden Rule:** Events lie last, logs lie less, metrics never lie. Cross-reference all three.

---

## Pattern Reference Table

| Pattern | Issues Affected |
|---|---|
| Resource misconfiguration | CrashLoop, OOMKilled, Eviction, Pending, HPA |
| Image / registry issues | ImagePullBackOff |
| Networking / DNS | DNS failures, Service unreachable, Ingress |
| Storage | PVC Pending, Eviction, CrashLoop |
| Security / RBAC | RBAC errors, ImagePull (private registry), Ingress TLS |
| Control plane | etcd, Cluster Autoscaler, Terminating resources |
| Scheduling | Pending pods, Node Pressure, Autoscaler |

---

## 1. Pod CrashLoopBackOff

### Description
The container starts, crashes immediately (or after a short time), and Kubernetes keeps restarting it with exponential back-off (10s → 20s → 40s → ... → 5m). The pod never reaches `Running` state sustainably.

### Root Causes
- Application exception or fatal error at startup (misconfigured env vars, missing DB connection)
- Missing or invalid ConfigMap / Secret mounts
- Failing liveness probe causing perpetual restarts
- Permission errors on mounted volumes
- Binary crashes (segfault, OOM at startup)
- Entrypoint / command mismatch between Dockerfile and pod spec

### Diagnosis

```bash
# Step 1: Identify the crash
kubectl get pods -n <ns>
# STATUS = CrashLoopBackOff, RESTARTS will be > 0

# Step 2: Get last crash logs (most important)
kubectl logs <pod-name> -n <ns> --previous

# Step 3: Current logs (if partially running)
kubectl logs <pod-name> -n <ns>

# Step 4: Describe for events and probe status
kubectl describe pod <pod-name> -n <ns>
# Look for: Exit Code, Last State, Liveness/Readiness probe failures

# Step 5: Check exit code
# Exit Code 1   → App crashed (check logs)
# Exit Code 137 → OOMKilled (SIGKILL) — see Issue #3
# Exit Code 139 → Segfault (SIGSEGV)
# Exit Code 2   → Misuse of shell built-in (bad entrypoint)

# Step 6: Exec into a running instance (if briefly alive)
kubectl exec -it <pod-name> -n <ns> -- /bin/sh

# Step 7: Check configmaps/secrets are populated correctly
kubectl get secret <secret-name> -n <ns> -o jsonpath='{.data}' | base64 -d
```

### Solutions

**Short-term:**
```bash
# Temporarily override the entrypoint to keep pod alive for inspection
# In pod spec:
command: ["sleep", "3600"]
# or
command: ["/bin/sh", "-c", "sleep infinity"]
# Then exec in and debug manually
```

**Long-term:**

| Root Cause | Fix |
|---|---|
| App crashes on missing env var | Add proper validation in app startup; use `envFrom` with `secretRef` |
| Liveness probe too aggressive | Increase `initialDelaySeconds`, `failureThreshold` |
| Volume permission error | Set `securityContext.fsGroup` or `runAsUser` on pod spec |
| Wrong entrypoint | Align `command`/`args` with Dockerfile `ENTRYPOINT`/`CMD` |

---

## 2. ImagePullBackOff / ErrImagePull

### Description
Kubernetes cannot pull the container image. The pod stays in `Pending` or transitions to `ImagePullBackOff`. `ErrImagePull` is the initial error; `ImagePullBackOff` is the retry state.

### Root Causes
- Image tag does not exist or was deleted (`latest` anti-pattern)
- Wrong image name / registry URL
- Private registry requires credentials not provided
- `imagePullSecret` missing, misconfigured, or in the wrong namespace
- Network policy blocking egress to registry
- Registry rate limiting (DockerHub unauthenticated = 100 pulls/6h)
- Insecure registry without `daemon.json` configuration on nodes

### Diagnosis

```bash
# Step 1: Check pod events
kubectl describe pod <pod-name> -n <ns>
# Look for: Failed to pull image, 401 Unauthorized, 404 Not Found, network timeout

# Step 2: Verify the image exists
docker pull <image:tag>
# Or use skopeo (no daemon needed):
skopeo inspect docker://<registry>/<image>:<tag>

# Step 3: Check imagePullSecrets exist in the correct namespace
kubectl get secret <secret-name> -n <ns>
kubectl get serviceaccount default -n <ns> -o yaml | grep imagePullSecrets

# Step 4: Validate the secret content
kubectl get secret <secret-name> -n <ns> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d

# Step 5: Check node-level Docker/containerd config for insecure registries
# SSH to node, then:
cat /etc/containerd/config.toml | grep -A5 registry
```

### Solutions

```bash
# Create a registry pull secret
kubectl create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<user> \
  --docker-password=<token> \
  --docker-email=<email> \
  -n <namespace>

# Attach to ServiceAccount
kubectl patch serviceaccount default -n <ns> \
  -p '{"imagePullSecrets": [{"name": "regcred"}]}'

# For DockerHub rate limiting — authenticate pulls
kubectl create secret docker-registry dockerhub-cred \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<user> \
  --docker-password=<token> -n <ns>
```

**Long-term:**
- Mirror all external images to a private registry (Harbor, ECR, Artifact Registry)
- Never use `latest` tag in production — always pin to immutable digests (`image@sha256:abc...`)
- Set up pull-through caches to avoid DockerHub rate limits

---

## 3. OOMKilled (Out of Memory)

### Description
The container's memory usage exceeded its `resources.limits.memory`, and the Linux OOM killer (or cgroup) sent `SIGKILL` (Exit Code 137). This appears as `OOMKilled: true` in pod state.

### Root Causes
- Memory limit set too low for actual workload requirements
- Memory leak in the application (heap never released)
- JVM / Node.js heap not tuned for container limits
- Spike traffic causing burst memory usage beyond limits
- Sidecar containers sharing the pod's memory budget
- Incorrect assumption about available memory (app reads host `/proc/meminfo` instead of cgroup limits)

### Diagnosis

```bash
# Step 1: Confirm OOMKilled
kubectl describe pod <pod-name> -n <ns>
# Look for: OOMKilled: true, Exit Code: 137, Last State reason: OOMKilled

# Step 2: Check current resource usage vs limits
kubectl top pod <pod-name> -n <ns> --containers

# Step 3: Historical memory trends (requires metrics-server or Prometheus)
# Prometheus query:
# container_memory_working_set_bytes{pod="<pod>", namespace="<ns>"}

# Step 4: Check node-level OOM events
kubectl describe node <node-name> | grep -A5 "OOM\|memory"
# Or check kernel logs on the node:
# journalctl -k | grep -i "oom\|killed process"

# Step 5: Look at current limits
kubectl get pod <pod-name> -n <ns> -o jsonpath='{.spec.containers[*].resources}'
```

### Solutions

**Immediate (stop the bleeding):**
```yaml
# Increase memory limit in deployment
resources:
  requests:
    memory: "512Mi"
  limits:
    memory: "1Gi"   # Bump limit, then monitor
```

**JVM-specific fix (critical):**
```bash
# JVM reads host memory by default — force container awareness
JAVA_OPTS: "-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"
# This caps JVM heap at 75% of the container's cgroup memory limit
```

**Node.js fix:**
```bash
node --max-old-space-size=768 app.js  # Set heap limit explicitly
```

**Long-term:**

| Action | Detail |
|---|---|
| Use VPA (Vertical Pod Autoscaler) in recommendation mode | Observe actual usage, then set limits accordingly |
| Heap profiling | Use pprof (Go), async_profiler (JVM), clinic.js (Node) |
| Set requests = limits for memory | Guarantees QoS class = Burstable → prevents eviction preference |
| Enable OOM alerting | Alert when `container_oom_events_total > 0` in Prometheus |

---

## 4. Pending Pods — Scheduling Failures

### Description
Pods remain in `Pending` state indefinitely. The scheduler cannot find a suitable node.

### Root Causes
- Insufficient CPU or memory on all available nodes
- Node selector / affinity rules cannot be satisfied
- Taints on nodes without matching tolerations
- `PodDisruptionBudget` blocking evictions needed to free space
- Topology spread constraints too strict
- Resource quota exhausted in the namespace
- No nodes in the required zone (zone-specific PVC)

### Diagnosis

```bash
# Step 1: Check events — scheduler always logs the reason
kubectl describe pod <pod-name> -n <ns>
# Look for: "Insufficient cpu", "0/5 nodes are available", "node(s) had taint"

# Step 2: Check resource quotas in namespace
kubectl describe resourcequota -n <ns>

# Step 3: Check node capacity vs requests (not actual usage!)
kubectl describe nodes | grep -A6 "Allocated resources"

# Step 4: Check taints
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints

# Step 5: Use scheduler simulation tool
kubectl get pod <pod-name> -n <ns> -o yaml | \
  kubectl alpha debug --copy-to=debug-pod --same-node ...

# Step 6: Check node labels for nodeSelector
kubectl get nodes --show-labels
```

### Solutions

```bash
# Case: Taint mismatch — add toleration to pod spec
tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gpu"
    effect: "NoSchedule"

# Case: Resource quota exhausted — check and increase
kubectl edit resourcequota <quota-name> -n <ns>

# Case: Cluster too small — trigger node scale-out (if Cluster Autoscaler present)
# Cluster Autoscaler will provision nodes automatically if properly configured
# Force it by checking CA logs:
kubectl logs -n kube-system -l app=cluster-autoscaler | tail -50
```

**Long-term:**
- Use `PodDisruptionBudgets` sparingly with realistic `minAvailable`
- Set `topologySpreadConstraints` with `whenUnsatisfiable: ScheduleAnyway` as a default
- Monitor `scheduler_pending_pods` metric in Prometheus
- Define `PriorityClasses` so critical workloads preempt lower-priority ones

---

## 5. DNS Resolution Failures

### Description
Pods cannot resolve service names (e.g., `myservice.mynamespace.svc.cluster.local`) or external domains. Manifests as `connection refused`, `unknown host`, or intermittent timeouts.

### Root Causes
- CoreDNS pods down or in CrashLoop
- CoreDNS misconfiguration (bad Corefile)
- `ndots:5` default causing excessive upstream lookups
- UDP packet loss at CNI level (common with Flannel + iptables)
- iptables rules corrupted or not properly applied
- Node-level DNS overloaded (too many queries per second)
- NodeLocal DNSCache not deployed, causing DNS amplification

### Diagnosis

```bash
# Step 1: Test DNS from within a pod
kubectl run dns-test --image=busybox:1.36 --restart=Never -it --rm \
  -- nslookup kubernetes.default.svc.cluster.local

# Step 2: Check CoreDNS pod health
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns

# Step 3: Check CoreDNS config
kubectl get configmap coredns -n kube-system -o yaml

# Step 4: Check CoreDNS metrics (if Prometheus scraping)
# coredns_dns_request_duration_seconds (latency)
# coredns_dns_responses_total{rcode="NXDOMAIN"} (failed lookups)

# Step 5: Check iptables / kube-proxy rules
iptables -t nat -L KUBE-SERVICES | grep dns

# Step 6: Run dnsutils for deeper diagnosis
kubectl run dnsutils --image=gcr.io/kubernetes-e2e-test-images/dnsutils:1.3 \
  --restart=Never -it --rm -- bash
# Then inside: dig kubernetes.default.svc.cluster.local @<coreDNS-ClusterIP>
```

### Solutions

```bash
# Increase CoreDNS replicas to handle load
kubectl scale deployment coredns --replicas=3 -n kube-system

# Fix ndots issue — reduce unnecessary upstream searches
# Add dnsConfig to pod spec:
dnsConfig:
  options:
    - name: ndots
      value: "2"    # Default is 5, which causes 5 lookup attempts before success

# Deploy NodeLocal DNSCache (major improvement for high-traffic clusters)
# https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/

# Tune CoreDNS cache:
# In Corefile, add: cache 30
```

**Common Corefile fix for forward DNS:**
```
.:53 {
    errors
    health
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
        pods insecure
        fallthrough in-addr.arpa ip6.arpa
    }
    forward . 8.8.8.8 8.8.4.4 {
        max_concurrent 1000
    }
    cache 30
    loop
    reload
    loadbalance
}
```

---

## 6. Service Not Reachable / Connectivity Issues

### Description
Pods can run but cannot communicate with a Service (ClusterIP, NodePort, or LoadBalancer). Symptoms include connection timeouts, connection refused, or intermittent packet loss.

### Root Causes
- Service selector labels don't match pod labels
- No healthy endpoints (all pods failing readiness probe)
- NetworkPolicy blocking traffic
- kube-proxy not running or iptables rules stale
- CNI plugin misconfiguration or crash
- Cloud load balancer misconfiguration (security groups, health checks)

### Diagnosis

```bash
# Step 1: Check if service has endpoints
kubectl get endpoints <service-name> -n <ns>
# If "<none>" — selector mismatch or pods failing readiness

# Step 2: Verify selector matches pod labels
kubectl get svc <service-name> -n <ns> -o yaml | grep selector
kubectl get pods -n <ns> --show-labels | grep <expected-label>

# Step 3: Check pod readiness
kubectl get pods -n <ns>
# READY column must be 1/1 (or N/N) for pods to appear as endpoints

# Step 4: Test connectivity from within cluster
kubectl run curl-test --image=curlimages/curl:8.1.0 --restart=Never -it --rm \
  -- curl -v http://<service-name>.<namespace>.svc.cluster.local:<port>

# Step 5: Check NetworkPolicies
kubectl get networkpolicy -n <ns>
kubectl describe networkpolicy <policy-name> -n <ns>

# Step 6: Check kube-proxy is running
kubectl get pods -n kube-system -l k8s-app=kube-proxy
kubectl logs -n kube-system <kube-proxy-pod>

# Step 7: Verify iptables rules exist for the service
kubectl get svc <service-name> -n <ns>   # Note ClusterIP
iptables -t nat -L | grep <ClusterIP>
```

### Solutions

```bash
# Fix selector mismatch — align labels
kubectl patch svc <svc-name> -n <ns> --type='json' \
  -p='[{"op":"replace","path":"/spec/selector/app","value":"correct-label"}]'

# If NetworkPolicy is blocking — add an allow rule
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
spec:
  podSelector:
    matchLabels:
      app: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080

# Restart kube-proxy if rules are stale
kubectl rollout restart daemonset kube-proxy -n kube-system
```

---

## 7. Node Pressure (Memory / Disk / PID)

### Description
Nodes emit `MemoryPressure`, `DiskPressure`, or `PIDPressure` conditions. The scheduler avoids placing pods on these nodes, and the kubelet may begin evicting pods.

### Root Causes
- **MemoryPressure:** High aggregate pod memory usage; system processes consuming memory
- **DiskPressure:** Log accumulation, image layer bloat, large emptyDir volumes, full `/var/lib/kubelet`
- **PIDPressure:** Fork-bombed processes, misconfigured pid limits, high connection counts per pod

### Diagnosis

```bash
# Step 1: Check node conditions
kubectl describe node <node-name> | grep -A10 "Conditions:"
# MemoryPressure, DiskPressure, PIDPressure should all be "False"

# Step 2: Check node resource usage
kubectl top node <node-name>

# Step 3: For DiskPressure — SSH to node and inspect
df -h                          # Disk usage overview
du -sh /var/lib/docker/*       # Or /var/lib/containerd
du -sh /var/log/pods/*         # Log volume
crictl images                  # List cached images

# Step 4: For MemoryPressure — check high consumers
kubectl top pods --all-namespaces --sort-by=memory | head -20

# Step 5: Kubelet eviction thresholds
cat /var/lib/kubelet/config.yaml | grep -A10 eviction
# Or: kubectl get --raw "/api/v1/nodes/<node>/proxy/configz" | jq '.kubeletconfig.evictionHard'
```

### Solutions

```bash
# DiskPressure — clean up images on node
crictl rmi --prune   # Remove unused images
# Or Docker:
docker system prune -af --volumes

# Tune kubelet eviction thresholds (in kubelet config)
evictionHard:
  memory.available: "200Mi"     # Default 100Mi — increase for earlier warning
  nodefs.available: "10%"       # Default 10%
  nodefs.inodesFree: "5%"
  imagefs.available: "15%"

evictionSoft:
  memory.available: "500Mi"
evictionSoftGracePeriod:
  memory.available: "1m30s"    # Gives pods time to gracefully shut down
```

**Long-term:**

| Issue | Prevention |
|---|---|
| Log bloat | Set `container log-max-size` in kubelet config; use fluentd/Loki centrally |
| Image bloat | Enable image GC policy (`imageGCHighThresholdPercent`) |
| Memory pressure | Deploy VPA; set realistic limits; monitor per-node memory allocation ratio |
| DiskPressure on `/tmp` | Avoid large emptyDir volumes; use PVCs |

---

## 8. PersistentVolume / PVC Issues

### Description
Pods cannot start because PersistentVolumeClaims (PVCs) are stuck in `Pending`, volumes fail to mount, or data becomes inaccessible.

### Root Causes
- No PV available matching PVC's `storageClassName`, access mode, or size
- Dynamic provisioner not installed or StorageClass misconfigured
- Volume already bound to a deleted pod (retained PV in `Released` state)
- Cloud provider quota exhausted (e.g., AWS EBS volume limits)
- ReadWriteMany requested but provisioner only supports ReadWriteOnce
- Zone mismatch — pod scheduled in zone-A, PV exists in zone-B

### Diagnosis

```bash
# Step 1: Check PVC state
kubectl get pvc -n <ns>
# STATUS: Pending = no matching PV found

# Step 2: Describe PVC for events
kubectl describe pvc <pvc-name> -n <ns>
# Look for: "no persistent volumes available", "storageclass not found"

# Step 3: Check available PVs
kubectl get pv
# Check: STATUS (Available/Bound/Released), STORAGECLASS, ACCESS MODES, CAPACITY

# Step 4: Check StorageClass
kubectl get storageclass
kubectl describe storageclass <name>

# Step 5: Check provisioner pod (e.g., EBS CSI driver)
kubectl get pods -n kube-system | grep csi
kubectl logs -n kube-system <csi-provisioner-pod> | tail -50

# Step 6: Zone mismatch check
kubectl get pvc <pvc-name> -n <ns> -o yaml | grep storageClassName
kubectl get pv <pv-name> -o yaml | grep topology
```

### Solutions

```bash
# Reclaim a Released PV for re-use
kubectl patch pv <pv-name> -p '{"spec":{"claimRef": null}}'

# Fix zone mismatch — use WaitForFirstConsumer binding mode
# In StorageClass:
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-wait
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer  # Delays PV creation until pod is scheduled
parameters:
  type: gp3

# For ReadWriteMany — use EFS (AWS), Filestore (GCP), or Azure Files
# Not all block storage supports RWX — check CSI driver documentation

# Force delete stuck PV (last resort)
kubectl patch pv <pv-name> -p '{"metadata":{"finalizers":null}}'
kubectl delete pv <pv-name> --grace-period=0 --force
```

---

## 9. Evicted Pods

### Description
Pods are terminated with reason `Evicted`. Unlike CrashLoopBackOff, the pod did not crash — the kubelet deliberately killed it due to resource pressure on the node.

### Root Causes
- Node MemoryPressure triggered kubelet eviction
- Node DiskPressure (most common cause in practice)
- Pod has `BestEffort` QoS class (no requests/limits set) → first to be evicted
- Preemption by higher-priority pod

### Diagnosis

```bash
# Step 1: Confirm eviction reason
kubectl describe pod <evicted-pod> -n <ns>
# Look for: "The node was low on resource: memory/disk"
# or: "Eviction threshold: memory.available<100Mi"

# Step 2: Check the node it was on
kubectl describe node <node-name> | grep -A20 "Events:"

# Step 3: List all evicted pods (for cleanup)
kubectl get pods --all-namespaces | grep Evicted

# Step 4: Bulk delete all evicted pods
kubectl get pods --all-namespaces --field-selector=status.phase==Failed \
  -o json | kubectl delete -f -
# Or targeted:
kubectl get pods -n <ns> | grep Evicted | awk '{print $1}' | xargs kubectl delete pod -n <ns>

# Step 5: Check pod QoS class
kubectl get pod <pod-name> -n <ns> -o jsonpath='{.status.qosClass}'
# BestEffort = evicted first, Burstable = next, Guaranteed = last
```

### Solutions

```yaml
# Always set resource requests and limits to avoid BestEffort QoS
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# For Guaranteed QoS (best eviction protection): requests == limits
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Long-term:**
- Assign `PriorityClass` to critical workloads to protect from preemption
- Monitor `kube_pod_status_reason{reason="Evicted"}` in Prometheus
- Set eviction alerting before pressure becomes critical

---

## 10. RBAC / Unauthorized Access Errors

### Description
Pods, users, or service accounts receive `403 Forbidden` or `Error from server (Forbidden)` when calling the Kubernetes API or accessing cluster resources.

### Root Causes
- ServiceAccount missing required ClusterRole / Role binding
- Using `default` ServiceAccount which has no permissions
- ClusterRoleBinding applied to wrong namespace ServiceAccount
- Wildcard (`*`) verb/resource accidentally removed during updates
- Webhook or operator using wrong ServiceAccount

### Diagnosis

```bash
# Step 1: Test specific permissions
kubectl auth can-i get pods --as=system:serviceaccount:<ns>:<sa-name> -n <ns>
kubectl auth can-i create deployments --as=system:serviceaccount:<ns>:<sa-name>

# Step 2: List what a ServiceAccount can do
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa-name>

# Step 3: Trace the error in pod logs
kubectl logs <pod-name> -n <ns> | grep -i "forbidden\|unauthorized\|403"

# Step 4: Check existing bindings for a ServiceAccount
kubectl get rolebindings,clusterrolebindings --all-namespaces \
  -o json | jq '.items[] | select(.subjects[]?.name=="<sa-name>")'

# Step 5: Find what roles are bound to a ServiceAccount
kubectl describe clusterrolebinding <binding-name>
```

### Solutions

```yaml
# Create a Role and bind it to a ServiceAccount
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: my-app-sa
  namespace: production
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

```bash
# Quick debug: temporarily grant cluster-admin (NEVER in prod permanently)
kubectl create clusterrolebinding debug-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=<ns>:<sa-name>
# Test, then immediately remove:
kubectl delete clusterrolebinding debug-admin
```

**Long-term:**
- Use `audit2rbac` tool to generate RBAC from audit logs automatically
- Enforce least-privilege by reviewing bindings quarterly
- Use `rbac-lookup` (Fairwinds) to visualize bindings

---

## 11. HorizontalPodAutoscaler (HPA) Not Scaling

### Description
HPA is configured but pods are not scaling up/down despite load changes, or the HPA shows `<unknown>` for metrics.

### Root Causes
- `metrics-server` not installed or not returning data
- Resources `requests` not defined (HPA can't calculate utilization %)
- Custom metrics adapter (KEDA, Prometheus Adapter) misconfigured
- `minReplicas == maxReplicas` (accidental lock)
- Cooldown period hasn't expired
- Metric name mismatch between HPA spec and adapter

### Diagnosis

```bash
# Step 1: Check HPA status
kubectl get hpa -n <ns>
# TARGETS column: <unknown>/50% = metrics-server issue
# 0%/50% = no traffic or wrong metric

# Step 2: Describe HPA for events and conditions
kubectl describe hpa <hpa-name> -n <ns>
# Look for: "failed to get cpu utilization", "unable to fetch metrics"

# Step 3: Verify metrics-server is running
kubectl get pods -n kube-system | grep metrics-server
kubectl top pods -n <ns>   # If this fails, metrics-server is the problem

# Step 4: Ensure resource requests are defined on the deployment
kubectl get deployment <name> -n <ns> -o jsonpath='{.spec.template.spec.containers[*].resources}'

# Step 5: Check metrics-server logs
kubectl logs -n kube-system -l k8s-app=metrics-server

# Step 6: For custom metrics (Prometheus Adapter)
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq .
```

### Solutions

```bash
# Install metrics-server (if missing)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For EKS/on-prem with self-signed certs, add args:
# --kubelet-insecure-tls
# --kubelet-preferred-address-types=InternalIP

# Ensure resource requests are set (required for CPU-based HPA)
resources:
  requests:
    cpu: "200m"    # HPA calculates: (actual_usage / requests) * 100 = utilization %

# Fix scaling bounds
spec:
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 60
```

**KEDA (custom metric scaling) debugging:**
```bash
kubectl get scaledobject -n <ns>
kubectl describe scaledobject <name> -n <ns>
kubectl logs -n kube-system -l app=keda-operator | tail -50
```

---

## 12. Ingress / TLS Misconfiguration

### Description
External traffic cannot reach services, HTTPS returns certificate errors, or HTTP-to-HTTPS redirects loop infinitely.

### Root Causes
- Ingress controller not installed or wrong IngressClass
- TLS secret missing, expired, or in wrong namespace
- Cert-manager not issuing certificates (ACME challenge failure)
- Backend service selector mismatch (no healthy endpoints)
- Annotation typos (`nginx.ingress.kubernetes.io/` prefix required for NGINX)
- Cloud LB health check path returns non-200

### Diagnosis

```bash
# Step 1: Check Ingress resource
kubectl get ingress -n <ns>
kubectl describe ingress <name> -n <ns>
# Look for: Address (should have IP/hostname), TLS section

# Step 2: Check Ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx | tail -100

# Step 3: Check TLS secret
kubectl get secret <tls-secret-name> -n <ns>
kubectl get secret <tls-secret-name> -n <ns> -o jsonpath='{.data.tls\.crt}' | \
  base64 -d | openssl x509 -noout -dates -subject

# Step 4: Cert-manager debugging (if used)
kubectl get certificate -n <ns>
kubectl describe certificate <cert-name> -n <ns>
kubectl get certificaterequest -n <ns>
kubectl get challenges -n <ns>   # ACME challenge status

# Step 5: Test backend connectivity from ingress controller pod
kubectl exec -it <ingress-pod> -n ingress-nginx -- \
  curl -v http://<service-name>.<ns>.svc.cluster.local:<port>
```

### Solutions

```yaml
# Correct Ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx           # Or use spec.ingressClassName
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - app.example.com
    secretName: app-tls-secret                   # Must exist in same namespace
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 8080
```

```bash
# Force cert-manager to re-issue certificate
kubectl delete certificate <cert-name> -n <ns>
# Cert-manager will recreate it automatically

# Check ACME HTTP01 challenge — temp pod + ingress must be accessible on port 80
kubectl get challenges -n <ns>
kubectl describe challenge <challenge-name> -n <ns>
```

---

## 13. etcd Performance / Data Issues

### Description
API server becomes slow or unresponsive, watches timeout, or `kubectl` commands hang. etcd is the backbone — if it degrades, the entire control plane degrades.

### Root Causes
- etcd disk I/O latency > 10ms (SSD required in production)
- etcd database file too large (default quota: 2GB)
- etcd leader election churning (network issues between etcd members)
- High object churn flooding etcd with events (e.g., flapping pods)
- Compaction not running — revision history bloat

### Diagnosis

```bash
# Step 1: Check etcd pod health
kubectl get pods -n kube-system -l component=etcd
kubectl logs -n kube-system etcd-<node> | grep -i "slow\|timeout\|leader\|error"

# Step 2: Check etcd metrics (port 2381)
kubectl exec -n kube-system etcd-<node> -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint status --write-out=table

# Step 3: Check DB size
# etcd_mvcc_db_total_size_in_bytes > 2GB = alarm imminent

# Step 4: Check latency
# etcd_disk_wal_fsync_duration_seconds{quantile="0.99"} > 10ms = disk issue

# Step 5: List alarms
etcdctl alarm list

# Step 6: Check revision count
etcdctl endpoint status -w json | jq '.[].Status.raftAppliedIndex'
```

### Solutions

```bash
# Compact etcd (reclaim space from old revisions)
# Get current revision
REV=$(etcdctl endpoint status --write-out="json" | \
  python3 -c "import json,sys; print(json.load(sys.stdin)[0]['Status']['header']['revision'])")

etcdctl compact $REV

# Defragment (reclaims space after compaction)
etcdctl defrag --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Clear alarm after space reclaimed
etcdctl alarm disarm

# Increase quota (if legitimate large clusters need it)
# Add to etcd manifest: --quota-backend-bytes=8589934592  (8GB)
```

**Long-term:**
- etcd must run on SSDs with dedicated disks (no shared with OS logs)
- Run automated compaction: `--auto-compaction-mode=periodic --auto-compaction-retention=1h`
- Set up etcd backup (daily snapshots via `etcdctl snapshot save`)
- Alert on `etcd_server_leader_changes_seen_total` — any change in production is notable

---

## 14. ConfigMap / Secret Misconfiguration

### Description
Applications crash or behave incorrectly due to missing, incorrect, or improperly mounted ConfigMaps and Secrets.

### Root Causes
- ConfigMap/Secret exists in wrong namespace
- Key name in `envFrom`/`valueFrom` doesn't match actual key in the map
- Binary data in ConfigMap (should use Secret with `binaryData`)
- Secret created from wrong base64 encoding (double-encoded)
- Volume mount path conflicts with application's expected path
- Immutable ConfigMap modified (rejected by API server)

### Diagnosis

```bash
# Step 1: Verify ConfigMap/Secret exists in correct namespace
kubectl get configmap <name> -n <ns>
kubectl get secret <name> -n <ns>

# Step 2: Inspect content
kubectl get configmap <name> -n <ns> -o yaml
kubectl get secret <name> -n <ns> -o jsonpath='{.data}' | \
  python3 -c "import sys,json,base64; [print(k,'=',base64.b64decode(v).decode()) for k,v in json.load(sys.stdin).items()]"

# Step 3: Check if env vars are visible inside the pod
kubectl exec -it <pod-name> -n <ns> -- env | grep <EXPECTED_VAR>

# Step 4: Check mounted files
kubectl exec -it <pod-name> -n <ns> -- ls -la /path/to/mount
kubectl exec -it <pod-name> -n <ns> -- cat /path/to/mount/<key>

# Step 5: Describe pod to see volume mount events
kubectl describe pod <pod-name> -n <ns> | grep -A5 "Mounts:\|Volumes:"
```

### Solutions

```yaml
# Correct envFrom usage
envFrom:
- configMapRef:
    name: app-config      # Must exist in same namespace as pod
- secretRef:
    name: app-secrets

# Correct single key injection
env:
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: db-secrets
      key: url            # Must exactly match the key in Secret data

# Volume mount (for config files)
volumes:
- name: app-config
  configMap:
    name: app-config
    items:                 # Optional: only mount specific keys
    - key: config.yaml
      path: config.yaml
containers:
- volumeMounts:
  - name: app-config
    mountPath: /etc/app    # Directory — config.yaml will be at /etc/app/config.yaml
    readOnly: true
```

```bash
# Fix double-encoded secret
echo -n "actual-password" | base64   # Do NOT base64 a string already in base64
kubectl create secret generic db-secret --from-literal=password=actual-password
```

---

## 15. Init Container Failures

### Description
A pod is stuck in `Init:Error` or `Init:CrashLoopBackOff`. Main containers never start because init containers must complete successfully first.

### Root Causes
- Init container script exits non-zero (dependency not ready)
- Init container waiting for a service that doesn't exist
- Database migration fails (wrong credentials, schema mismatch)
- Incorrect init container image or command
- Init container timeout (no timeout by default — can block forever)

### Diagnosis

```bash
# Step 1: Identify which init container is failing
kubectl get pod <pod-name> -n <ns>
# STATUS: Init:0/2 = 0 of 2 init containers complete

# Step 2: Get logs from failing init container
kubectl logs <pod-name> -n <ns> -c <init-container-name>
kubectl logs <pod-name> -n <ns> -c <init-container-name> --previous

# Step 3: List all containers (main + init)
kubectl get pod <pod-name> -n <ns> \
  -o jsonpath='{.spec.initContainers[*].name}'

# Step 4: Describe for events
kubectl describe pod <pod-name> -n <ns>

# Step 5: Exec into init container if running
kubectl exec -it <pod-name> -n <ns> -c <init-container-name> -- sh
```

### Solutions

```yaml
# Robust wait-for-dependency init container pattern
initContainers:
- name: wait-for-db
  image: busybox:1.36
  command:
  - sh
  - -c
  - |
    until nc -z db-service 5432; do
      echo "Waiting for database..."
      sleep 2
    done
    echo "Database is ready"
  # Add a timeout to prevent infinite wait
  # Use a sidecar or job for actual migration logic
```

```bash
# If init container image is wrong
kubectl set image pod/<pod-name> <init-container-name>=<correct-image> -n <ns>
# Note: You typically patch the Deployment, not the pod directly

kubectl patch deployment <deploy-name> -n <ns> \
  --type=json \
  -p='[{"op":"replace","path":"/spec/template/spec/initContainers/0/image","value":"<new-image>"}]'
```

---

## 16. Cluster Autoscaler Failures

### Description
Cluster Autoscaler (CA) should add nodes when pods are Pending and remove underutilized nodes, but fails to do either — causing either resource starvation or unexpected cost.

### Root Causes
- CA not deployed or misconfigured IAM/permissions (AWS: can't call Auto Scaling APIs)
- Pods have `PodDisruptionBudget` with `minAvailable` set too high — blocks scale-down
- Pods use local storage (`emptyDir`, `hostPath`) — CA won't evict these
- Node groups not configured in CA (`--nodes` flag missing new node groups)
- Scale-down disabled (`--scale-down-enabled=false`)
- Annotation `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` on pods

### Diagnosis

```bash
# Step 1: Check CA pod
kubectl get pods -n kube-system -l app=cluster-autoscaler
kubectl logs -n kube-system -l app=cluster-autoscaler | tail -100

# Step 2: Look for scale-up/down decisions in logs
kubectl logs -n kube-system -l app=cluster-autoscaler | \
  grep -E "scale up|scale down|not eligible|cannot be removed"

# Step 3: Check which pods are blocking scale-down
kubectl logs -n kube-system -l app=cluster-autoscaler | grep "not removable"

# Step 4: Check status ConfigMap (CA writes its status here)
kubectl get configmap cluster-autoscaler-status -n kube-system -o yaml

# Step 5: Verify IAM permissions (AWS EKS)
# CA needs: autoscaling:DescribeAutoScalingGroups, autoscaling:SetDesiredCapacity, etc.
aws iam simulate-principal-policy \
  --policy-source-arn <ca-role-arn> \
  --action-names autoscaling:SetDesiredCapacity
```

### Solutions

```bash
# Allow CA to evict pods blocking scale-down
kubectl annotate pod <pod-name> -n <ns> \
  cluster-autoscaler.kubernetes.io/safe-to-evict=true

# Check and fix PodDisruptionBudgets that are too restrictive
kubectl get pdb -n <ns>
kubectl describe pdb <pdb-name> -n <ns>
# If minAvailable = replicas count, scale-down is blocked

# Force CA to re-evaluate (restart CA pod)
kubectl rollout restart deployment cluster-autoscaler -n kube-system
```

**Long-term:**
- Use `Expander: least-waste` strategy for cost-optimal scaling
- Set `--skip-nodes-with-local-storage=false` only if you understand the implications
- Tag node groups with correct `k8s.io/cluster-autoscaler/<cluster-name>: owned` tags
- Consider Karpenter (AWS) as a faster, more flexible alternative to CA

---

## 17. Zombie / Terminating Namespaces and Resources

### Description
A namespace or resource is stuck in `Terminating` state indefinitely, blocking cleanup and sometimes causing cascading issues with operators.

### Root Causes
- Finalizers on resources not cleared by the responsible controller
- Custom Resource Definition (CRD) deleted before its instances were cleaned up
- Controller or operator responsible for the finalizer is no longer running
- Webhook blocking delete operations
- etcd connectivity issues preventing finalizer removal

### Diagnosis

```bash
# Step 1: Identify stuck resources
kubectl get namespace <ns>
# STATUS: Terminating

# Step 2: Check what's blocking namespace deletion
kubectl get all -n <ns>
# Check for remaining resources

# Step 3: Check finalizers on the namespace
kubectl get namespace <ns> -o jsonpath='{.spec.finalizers}'
kubectl get namespace <ns> -o yaml | grep finalizers -A10

# Step 4: Find custom resources with finalizers
kubectl api-resources --verbs=list --namespaced -o name | \
  xargs -I {} kubectl get {} -n <ns> --ignore-not-found 2>/dev/null

# Step 5: Check for blocking webhooks
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
kubectl describe validatingwebhookconfiguration <name> | grep -A5 "Namespace\|Failure"
```

### Solutions

```bash
# Remove finalizers from a stuck resource
kubectl patch namespace <ns> -p '{"spec":{"finalizers":[]}}' --type=merge
# Or using raw API:
kubectl proxy &
curl -X PUT http://localhost:8001/api/v1/namespaces/<ns>/finalize \
  -H "Content-Type: application/json" \
  -d '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"<ns>"},"spec":{"finalizers":[]}}'

# Remove finalizers from a specific stuck resource
kubectl patch <resource-type> <name> -n <ns> \
  -p '{"metadata":{"finalizers":[]}}' --type=merge

# Force delete (last resort — may cause orphaned cloud resources)
kubectl delete namespace <ns> --grace-period=0 --force

# Fix blocking webhook (temporarily disable during cleanup)
kubectl delete validatingwebhookconfiguration <webhook-name>
# Recreate after cleanup is done
```

> **Warning:** Removing finalizers manually can leave orphaned cloud resources (load balancers, PVs, etc.). Always check what the finalizer was protecting before forcing removal.

---

## Quick Reference: Debugging Command Cheat Sheet

```bash
# ─── Pod State ───────────────────────────────────────────────────────────────
kubectl get pods -n <ns> -o wide                         # Node placement
kubectl describe pod <pod> -n <ns>                       # Full details + events
kubectl logs <pod> -n <ns> --previous -c <container>     # Last crash logs
kubectl exec -it <pod> -n <ns> -- /bin/sh                # Shell into pod

# ─── Events ──────────────────────────────────────────────────────────────────
kubectl get events -n <ns> --sort-by='.lastTimestamp'    # Recent events
kubectl get events --all-namespaces --field-selector=type=Warning

# ─── Resources ───────────────────────────────────────────────────────────────
kubectl top nodes                                         # Node CPU/Memory
kubectl top pods -n <ns> --containers                    # Pod-level
kubectl describe node <node> | grep -A8 "Allocated"      # Allocation pressure

# ─── Networking ──────────────────────────────────────────────────────────────
kubectl get endpoints <svc> -n <ns>                      # Endpoint health
kubectl get networkpolicy -n <ns>                        # Active policies
kubectl run tmp --image=curlimages/curl -it --rm -- sh   # Ad-hoc debug pod

# ─── Storage ─────────────────────────────────────────────────────────────────
kubectl get pv,pvc -n <ns>                               # PV/PVC status
kubectl describe pvc <pvc> -n <ns>                       # Provisioning events

# ─── RBAC ────────────────────────────────────────────────────────────────────
kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>

# ─── Control Plane ───────────────────────────────────────────────────────────
kubectl get componentstatuses                             # etcd, scheduler, controller
kubectl cluster-info dump | grep -A5 "etcd\|error"
```

---

## Recommended Observability Stack

| Layer | Tool | Key Metrics / Alerts |
|---|---|---|
| Metrics | Prometheus + kube-state-metrics | `kube_pod_container_status_restarts_total`, `container_oom_events_total` |
| Dashboards | Grafana | Kubernetes cluster overview, namespace dashboards |
| Logging | Fluent Bit → Loki / Elasticsearch | Error log rates, crash patterns |
| Tracing | Jaeger / Tempo | Latency spikes, inter-service errors |
| Alerting | AlertManager | CrashLoop, OOM, PVC pending, node pressure |
| Profiling | Parca / Pyroscope | Continuous CPU/memory profiling |
| Policy | Kyverno / OPA Gatekeeper | Enforce resource limits, deny privilege escalation |

---

*Guide version: April 2026 | Kubernetes 1.28–1.30 | Validate against your cluster version for API differences.*
