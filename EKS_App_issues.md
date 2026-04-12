# EKS & Application Issues — Complete Guide

> This guide covers real-world issues that happen when running a
> **game or payment application on AWS EKS**.
> Every issue has: plain English explanation → real sample output →
> diagnosis steps → fix.
>
> `# ⚠️ PROBLEM →` the broken value
> `# ✅ HEALTHY →` what it looks like when fixed
> `# 💡 MEANS  →` plain English explanation

---

# PART 1 — HTTP Error Codes

> HTTP errors are what **users see** in their browser or app.
> They are the starting point — then you dig into logs to find why.

---

## HTTP 400 — Bad Request

### What Is Happening?

The user (or frontend app) sent a request with **wrong or missing data**.
Like filling out a form but leaving required fields blank — the server rejects it.

### Sample — What the User Sees

```
POST /api/payment
Status: 400 Bad Request
Body: {
  "error": "Validation failed",
  "details": [
    "amount: must be a number, got string 'hundred'",   ← ⚠️ PROBLEM
    "currency: is required but was not provided"         ← ⚠️ PROBLEM
  ]
}
```

### Sample — What Logs Show

```bash
$ kubectl logs payment-service-xxx -n production
```
```
2026-04-12 10:05:33 ERROR  ValidationError: Request body failed validation
                           Field 'amount' expected number, received string    # ⚠️ PROBLEM
                           Field 'currency' is missing                        # ⚠️ PROBLEM
                           IP: 203.0.113.45
                           Endpoint: POST /api/payment
```

### In New Relic

```
APM → Errors → TransactionError
  Error class: ValidationError
  Message: Request body failed validation
  Count: 450 in last 30 min   ← spike means frontend sending wrong data
```

### Diagnose

```bash
# Step 1 — Check error rate in New Relic APM
# APM → my-service → Errors → filter by "400"

# Step 2 — Find which endpoint is causing most 400s
# APM → Transactions → sort by Error Rate

# Step 3 — Read logs to see exact validation failure
kubectl logs -n production -l app=payment-service --tail=50 | grep "400\|Validation\|Bad Request"

# Step 4 — Check if it started after a frontend deployment
# APM → Deployments → did 400 rate spike after last deploy?
```

### Fix

```
400 from your own app:
  → Fix the frontend to send correct data format
  → Or make the API more lenient (accept both string and number for amount)

400 from external API (Stripe, bank):
  → Check your request format matches their API documentation
  → Add request logging to see exactly what you are sending them
```

---

## HTTP 401 — Unauthorized

### What Is Happening?

The user has **no valid identity token** — either not logged in, token expired, or token is wrong.
Like showing up to a members-only club without your membership card.

### Sample — What the User Sees

```
GET /api/account/balance
Status: 401 Unauthorized
Body: {
  "error": "Token expired",              ← ⚠️ PROBLEM: user session expired
  "message": "Please log in again"
}
```

### Sample — API Gateway Log (AWS CloudWatch)

```
{
  "requestId": "abc-123",
  "status": 401,
  "message": "The incoming token has expired",   # ⚠️ PROBLEM → JWT token expired
  "path": "/api/account/balance",
  "authorizer": "CognitoJWTAuthorizer"           # 💡 Cognito rejected the token
}
```

### Sample — What Logs Show in Kubernetes

```bash
$ kubectl logs api-gateway-xxx -n production | grep "401"
```
```
2026-04-12 10:10:45 WARN   JWT validation failed for /api/account/balance
                           Reason: Token expired at 2026-04-12T10:05:00Z   # ⚠️ PROBLEM
                           Current time: 2026-04-12T10:10:45Z
                           # Token expired 5 minutes ago — user was idle too long
```

### Diagnose

```bash
# Step 1 — Confirm it is 401 and how many users affected
# New Relic APM → Transactions → filter status = 401
# If count is rising → token expiry or auth service down

# Step 2 — Check if Cognito / auth service is healthy
kubectl get pods -n production | grep auth
kubectl logs auth-service-xxx -n production | grep "ERROR\|error" | tail -20

# Step 3 — Check JWT token expiry setting
kubectl describe configmap auth-config -n production | grep "TOKEN_EXPIRY\|JWT_TTL"
```

### Fix

```
Short-lived token (users get logged out too fast):
  → Increase JWT token expiry time
  → Implement silent token refresh (refresh token before expiry)

Auth service down:
  → kubectl rollout restart deployment auth-service -n production

Cognito config wrong (wrong audience/issuer):
  → Check JWT authorizer in API Gateway matches your Cognito User Pool
```

---

## HTTP 403 — Forbidden

### What Is Happening?

The user IS logged in, but they are **not allowed to do what they are trying to do**.
Like a regular employee trying to open the CEO's office — they are known, just not permitted.

### Sample — What the User Sees

```
DELETE /api/admin/users/456
Status: 403 Forbidden
Body: {
  "error": "Access denied",
  "message": "Admin role required for this action",   # ⚠️ PROBLEM → user has wrong role
  "userRole": "viewer",
  "requiredRole": "admin"
}
```

### Sample — Kubernetes Pod RBAC Failure

```bash
$ kubectl logs payment-processor-xxx -n production
```
```
2026-04-12 10:15:00 ERROR  Kubernetes API call failed
                           Action: GET secrets/payment-api-keys
                           Namespace: production
                           Error: User "system:serviceaccount:production:payment-processor"
                                  cannot get resource "secrets"
                                  403 Forbidden                              # ⚠️ PROBLEM
                           # 💡 MEANS → pod's service account has no permission to read secrets
```

### Sample — AWS IAM Failure (Pod trying to access S3)

```bash
$ kubectl logs receipt-generator-xxx -n production
```
```
2026-04-12 10:16:00 ERROR  An error occurred (AccessDenied) when calling
                           the PutObject operation:
                           User: arn:aws:sts::497041484428:assumed-role/eks-node-role/i-xxx
                           is not authorized to perform: s3:PutObject
                           on resource: arn:aws:s3:::receipts-bucket/receipt-001.pdf
                           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                           # ⚠️ PROBLEM → IAM role does not have s3:PutObject permission
```

### Diagnose

```bash
# Check app-level 403 (user role issue)
# New Relic APM → Errors → filter 403
# Check which endpoint and which user role is failing

# Check Kubernetes RBAC 403
kubectl auth can-i get secrets \
  --as=system:serviceaccount:production:payment-processor \
  -n production
# Output: "no" → ⚠️ PROBLEM
# Output: "yes" → ✅ HEALTHY

# Check AWS IAM 403
kubectl exec payment-processor-xxx -n production -- \
  aws sts get-caller-identity
# Shows what IAM role the pod is using
# Then check that role's policies in AWS console
```

### Fix

```bash
# Fix Kubernetes RBAC
kubectl create role secret-reader \
  --verb=get,list \
  --resource=secrets \
  -n production
kubectl create rolebinding payment-secret-reader \
  --role=secret-reader \
  --serviceaccount=production:payment-processor \
  -n production

# Fix AWS IAM — add policy to the IAM role used by the pod
# AWS Console → IAM → Roles → eks-node-role → Add permission → s3:PutObject
```

---

## HTTP 404 — Not Found

### What Is Happening?

The thing the user is asking for **does not exist** — wrong URL, deleted resource, or routing not set up.
Like asking for a product that was removed from the store.

### Sample — Ingress Path Missing

```bash
$ curl -v https://payment.devopscab.com/api/v2/payment
```
```
< HTTP/1.1 404 Not Found
< Content-Type: text/html

# Ingress controller logs:
$ kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx | grep "404"
```
```
[warn]  no matching rule found for request
        Host: payment.devopscab.com
        Path: /api/v2/payment       # ⚠️ PROBLEM → ingress only has rule for /api/v1/*
                                    # /api/v2 path was never added to ingress
```

### Sample — Pod Scaled to Zero

```bash
$ kubectl get pods -n production | grep payment
```
```
# No output — no pods running   # ⚠️ PROBLEM → HPA scaled to 0 at night (low traffic period)
                                 # Morning traffic arrives, no pods to handle it → 404
```

```bash
$ kubectl get hpa -n production
```
```
NAME           REFERENCE               MINPODS   REPLICAS
payment-hpa    Deployment/payment      0         0        # ⚠️ PROBLEM → minPods=0, scaled to 0
```

### Diagnose

```bash
# Step 1 — Check if pods are running
kubectl get pods -n production | grep payment
# If empty → scaled to 0 or all crashing

# Step 2 — Check ingress rules
kubectl describe ingress payment-ingress -n production
# Look for: Rules section → list all defined paths

# Step 3 — Check service endpoints
kubectl get endpoints payment-svc -n production
# If <none> → service has no pods → returns 404
```

### Fix

```bash
# Fix: Pods scaled to 0
kubectl scale deployment payment -n production --replicas=2

# Fix: HPA minPods too low
kubectl patch hpa payment-hpa -n production \
  -p '{"spec":{"minReplicas":2}}'

# Fix: Missing ingress path
kubectl edit ingress payment-ingress -n production
# Add the missing path: /api/v2/*
```

---

## HTTP 408 — Request Timeout

### What Is Happening?

The **client** (browser/app) connected but took too long to send the full request.
Common with large file uploads or slow mobile connections.

### Sample — ALB Access Log

```
2026-04-12T10:20:00 POST /api/upload 408 -
  target: 10.0.1.45:8080
  request_processing_time: 61.234
  target_processing_time: -1
  response_processing_time: -1
  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
  # ⚠️ PROBLEM → took 61 seconds, ALB timeout is 60s → cut off
  # target_processing_time: -1 means request never reached the pod
```

### Fix

```
In AWS Console:
  EC2 → Load Balancers → select your ALB
  → Attributes → Idle timeout → change from 60s to 300s

For file uploads: use pre-signed S3 URLs instead
  (client uploads directly to S3, skipping your pod entirely)
```

---

## HTTP 429 — Too Many Requests

### What Is Happening?

Someone (or your own app) is sending **too many requests too fast**. A rate limiter is saying "slow down".

### Sample — API Gateway Throttling

```bash
$ curl -v https://payment.devopscab.com/api/payment
```
```
< HTTP/1.1 429 Too Many Requests
< Retry-After: 30
< X-RateLimit-Limit: 100
< X-RateLimit-Remaining: 0       # ⚠️ PROBLEM → 0 requests left in this time window
< X-RateLimit-Reset: 1744452030

{
  "message": "Rate limit exceeded. You have made 100 requests in the last 60 seconds.
              Please wait 30 seconds before trying again."
}
```

### Sample — App Logs (Payment Gateway Rate Limit)

```bash
$ kubectl logs payment-service-xxx -n production
```
```
2026-04-12 10:25:00 ERROR  Stripe API call failed
                           Status: 429 Too Many Requests
                           Message: Too many requests; please slow down
                           Rate limit: 100 req/s
                           Current rate: 340 req/s     # ⚠️ PROBLEM → sending 3.4x too fast
                           Retry-After: 2 seconds
```

### Diagnose

```bash
# Step 1 — Check rate in New Relic
# APM → Transactions → /api/payment → Throughput → what is the req/s right now?

# Step 2 — Check if 429 started after a specific event (game launch, sale, bot)
# New Relic → Logs → search "429" → check timestamp pattern

# Step 3 — Check if it is coming FROM your app TO external API
kubectl logs payment-service-xxx -n production | grep "429\|rate limit\|Too Many" | tail -20
```

### Fix

```bash
# Fix 1 — Add retry with backoff in your code (not a Kubernetes fix)
# When you get 429, wait and retry:
# Attempt 1 → 429 → wait 2s
# Attempt 2 → 429 → wait 4s
# Attempt 3 → 429 → wait 8s  (exponential backoff)

# Fix 2 — Queue requests instead of sending all at once
# Use SQS to buffer payment requests
# Worker processes them at a controlled rate

# Fix 3 — Request higher rate limit from AWS / Stripe / bank
# AWS API Gateway → Usage Plans → increase rate limit
```

---

## HTTP 500 — Internal Server Error

### What Is Happening?

Something **crashed inside your application**. The app did not expect this situation and threw an unhandled error.
Like the chef trying to cook a dish and accidentally setting the kitchen on fire.

### Sample — App Logs

```bash
$ kubectl logs payment-service-xxx -n production --previous
```
```
2026-04-12 10:30:00 ERROR  Unhandled exception in POST /api/payment
                           java.lang.NullPointerException            # ⚠️ PROBLEM → code bug
                             at PaymentService.processPayment(PaymentService.java:142)
                             at PaymentController.handleRequest(PaymentController.java:67)
                           # 💡 MEANS → code tried to use a variable that was null/empty
                           # Root cause: fraud check returned null instead of a score
                           #             PaymentService did not handle the null case
```

### Sample — New Relic APM Error

```
APM → Errors → TransactionError

Error Class:  NullPointerException
Message:      Cannot invoke method getScore() on null object
Affected Transactions: 847 in last 30 min    # ⚠️ PROBLEM → 847 payments failed
Stack Trace:
  PaymentService.java:142 → processPayment()
  FraudCheckClient.java:89 → getScore()
  # 💡 Fraud check service returned null → not handled → 500
```

### Diagnose

```bash
# Step 1 — Find the 500 in New Relic
# APM → Errors → click the error → read full stack trace
# The stack trace shows exactly which line of code failed

# Step 2 — Check logs around the time it started
kubectl logs payment-service-xxx -n production | grep -B5 "500\|ERROR\|Exception" | head -50

# Step 3 — Check if it started after a deployment
kubectl rollout history deployment/payment-service -n production
# Did 500 rate go up after a specific revision?

# Step 4 — Check if downstream service is returning bad data
kubectl logs fraud-check-xxx -n production | tail -30
```

### Fix

```bash
# Immediate fix — rollback if it started after a deployment
kubectl rollout undo deployment/payment-service -n production

# Long-term fix — handle the null case in code
# Before: String score = fraudCheck.getScore();
# After:  String score = fraudCheck != null ? fraudCheck.getScore() : "unknown";
```

---

## HTTP 502 — Bad Gateway

### What Is Happening?

The Load Balancer (ALB) reached your pod, but the pod gave back a **broken or no response**.
Like calling someone whose phone connects but all you hear is static.

### Sample — During Rolling Deployment

```
ALB Access Log:
  10:35:00  POST /api/payment  502  target: 10.0.1.45:8080
                                    elb_status_code: 502
                                    target_status_code: -    # ← pod never responded
                                    error_reason: Target.Timeout
```

```bash
$ kubectl get pods -n production
```
```
NAME                    READY   STATUS             AGE
payment-old-7d6f9-xxx   1/1     Terminating        5m    # ← old pod being killed
payment-new-8e7g0-xxx   0/1     Running            30s   # ← new pod not ready yet
                         ↑↑↑
                         # ⚠️ PROBLEM → new pod is Running but NOT READY (0/1)
                         # ALB sends traffic to it anyway → pod not listening → 502
```

### Sample — Wrong Port in Service

```bash
$ kubectl describe svc payment-svc -n production
```
```
Port:       80/TCP
TargetPort: 80/TCP      # ⚠️ PROBLEM → service says port 80
```

```bash
$ kubectl describe pod payment-xxx -n production
```
```
Containers:
  payment:
    Port: 8080/TCP      # ⚠️ PROBLEM → app actually listens on 8080
                        # Service sends to 80, app is on 8080 → 502
```

### Diagnose

```bash
# Step 1 — Check if pods are ready
kubectl get pods -n production | grep payment
# READY column: 0/1 = pod running but not ready → causes 502

# Step 2 — Check service target port matches container port
kubectl describe svc payment-svc -n production | grep -i "port\|targetport"
kubectl describe pod payment-xxx -n production | grep -i "port"
# Compare these two — they must match

# Step 3 — Check ALB target group health in AWS Console
# EC2 → Load Balancers → Target Groups → check health status of each target
```

### Fix

```bash
# Fix wrong port
kubectl patch svc payment-svc -n production \
  -p '{"spec":{"ports":[{"port":80,"targetPort":8080}]}}'

# Fix pods not ready during deployment
# Add proper readiness probe so ALB waits until pod is actually ready:
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
```

---

## HTTP 503 — Service Unavailable

### What Is Happening?

Your service exists, the Load Balancer can reach it, but **no healthy pods are available** to handle requests. The shop is there but nobody is behind the counter.

### Sample — All Pods Crashing

```bash
$ kubectl get pods -n production
```
```
NAME                    READY   STATUS             RESTARTS   AGE
payment-7d6f9-aaa       0/1     CrashLoopBackOff   12         20m   # ⚠️ PROBLEM
payment-7d6f9-bbb       0/1     CrashLoopBackOff   12         20m   # ⚠️ PROBLEM
payment-7d6f9-ccc       0/1     CrashLoopBackOff   12         20m   # ⚠️ PROBLEM
# All 3 pods crashing → 0 healthy targets → ALB returns 503 for every request
```

### Sample — Database Connection Pool Full

```bash
$ kubectl logs payment-xxx -n production
```
```
2026-04-12 10:40:00 ERROR  Cannot acquire database connection
                           Pool exhausted: all 20 connections in use    # ⚠️ PROBLEM
                           Wait timeout: 30000ms exceeded
                           Active connections: 20/20
                           Pending requests: 847                        # ⚠️ PROBLEM → 847 waiting
```

```bash
# In New Relic APM — what this looks like:
Transactions:
  /api/payment    avg duration: 30.1s    error rate: 95%    # ⚠️ PROBLEM
  # 30 seconds = all requests waiting for a DB connection then timing out
```

### Diagnose

```bash
# Step 1 — Check pod count and health
kubectl get pods -n production | grep payment
# Are any 1/1 Running? If none → 503 for all users

# Step 2 — Check HPA to see if it is scaling
kubectl get hpa -n production
# Are REPLICAS at 0? Is HPA unable to scale?

# Step 3 — Check DB connection count
kubectl exec payment-xxx -n production -- \
  psql -U appuser -c "SELECT count(*) FROM pg_stat_activity;"
# If count is at max_connections → pool exhausted

# Step 4 — Check ALB target group
# AWS Console → EC2 → Target Groups → how many healthy targets?
```

### Fix

```bash
# Fix: All pods crashing → identify root cause
kubectl logs payment-xxx -n production --previous
# Fix the crash, then:
kubectl rollout restart deployment payment -n production

# Fix: DB connection pool exhausted → use RDS Proxy
# AWS Console → RDS → Create RDS Proxy → point your pods to the proxy
# RDS Proxy manages connections → 50 pods sharing 20 connections efficiently
```

---

## HTTP 504 — Gateway Timeout

### What Is Happening?

The Load Balancer connected to your pod and waited for a response. The pod took too long (beyond the timeout limit) and the Load Balancer gave up.

Like placing a food order and waiting 2 hours — you eventually give up and leave.

### Sample — ALB Access Log

```
10:45:00 GET /api/report/annual 504
  target: 10.0.1.45:8080
  target_processing_time: 61.003    # ⚠️ PROBLEM → pod took 61 seconds
  elb_status_code: 504              # ⚠️ PROBLEM → ALB timeout is 60s → gave up at 61s
```

### Sample — App Logs Showing Slow DB Query

```bash
$ kubectl logs report-service-xxx -n production
```
```
2026-04-12 10:45:00 INFO   Starting annual report generation for user 12345
2026-04-12 10:45:00 INFO   Running query: SELECT * FROM transactions WHERE year=2025...
2026-04-12 10:46:05 ERROR  Query timeout after 65000ms                 # ⚠️ PROBLEM
                           Table: transactions (45 million rows)        # 💡 huge table
                           Missing index on: year, user_id             # ⚠️ ROOT CAUSE
                           Full table scan required                    # 💡 scans all 45M rows
```

### Sample — Slow External API Call

```bash
$ kubectl logs payment-xxx -n production
```
```
2026-04-12 10:50:00 INFO   Calling bank API for fraud verification...
2026-04-12 10:51:02 ERROR  Request to bank API timed out after 62000ms  # ⚠️ PROBLEM
                           URL: https://api.bankname.com/verify
                           No timeout configured on HTTP client          # ⚠️ ROOT CAUSE
                           # 💡 MEANS → app waited 62 seconds for bank API with no timeout set
```

### In New Relic

```
APM → Distributed Tracing → click a slow request

Trace breakdown:
  payment-service.processPayment        2ms      ← fast
  fraud-check-service.checkFraud        1ms      ← fast
  bank-api-client.verifyTransaction    61,003ms  ← ⚠️ PROBLEM → bank API is the bottleneck
                                        ↑↑↑↑↑
  # Distributed Tracing shows you EXACTLY which service/step is slow
```

### Diagnose

```bash
# Step 1 — Find slow transactions in New Relic
# APM → Transactions → sort by Duration → find the 60s+ ones
# Click one → "Trace details" → see which step took the longest

# Step 2 — Check if it is DB-related
# APM → Databases → find slowest queries

# Step 3 — Check if it is an external API call
kubectl logs <service>-xxx -n production | grep "timeout\|timed out\|60000\|took.*ms" | tail -20

# Step 4 — Check CPU throttling (can also cause 504)
kubectl top pods -n production
# If CPU is at limit → all requests slow → 504
```

### Fix

```bash
# Fix slow DB query — add missing index
kubectl exec -it db-pod -n database -- \
  psql -U appuser -d mydb -c \
  "CREATE INDEX idx_transactions_year_user ON transactions(year, user_id);"

# Fix external API timeout — always set timeouts in code
# Before: httpClient.get("https://api.bank.com/verify")
# After:  httpClient.get("https://api.bank.com/verify", timeout=10000)
#         (10 seconds max, then fail fast and return error to user)

# Fix CPU throttling causing 504
kubectl edit deployment <service> -n production
# Increase CPU limit
```

---

# PART 2 — Slowness Issues (No Error, But Painful)

---

## Slow Database Queries

### What Is Happening?

The app is running fine but every request is slow because the database is taking too long to respond. Like asking a librarian to find a book but the library has no catalogue — they have to check every shelf.

### Sample — App Logs

```bash
$ kubectl logs payment-service-xxx -n production
```
```
2026-04-12 11:00:00 DEBUG  Executing query: SELECT * FROM orders WHERE user_id = 9876
2026-04-12 11:00:08 DEBUG  Query completed. Rows: 1. Duration: 8234ms   # ⚠️ PROBLEM → 8 seconds!
                           # 💡 MEANS → 8 seconds for one simple query = missing index on user_id
```

### In New Relic

```
APM → Databases tab

Slowest Queries (last 30 min):
  Query                                    Avg Duration   Count
  SELECT * FROM orders WHERE user_id=?     8,234ms        2,450   # ⚠️ PROBLEM → 8s per query
  SELECT * FROM payments WHERE amount>0    12,100ms       890     # ⚠️ PROBLEM → 12s (full scan)
  INSERT INTO audit_log VALUES (...)       45ms           50,000  # ✅ HEALTHY → fast
```

### Diagnose

```bash
# Step 1 — New Relic APM → Databases → find slowest queries
# Note the exact query and which table it runs on

# Step 2 — Check if index exists
kubectl exec -it postgres-0 -n database -- \
  psql -U appuser -d mydb -c "\d orders"
# Look for: Indexes section
# If user_id is not listed → missing index → full table scan

# Step 3 — Check table size (large table = slow query without index)
kubectl exec -it postgres-0 -n database -- \
  psql -U appuser -d mydb -c \
  "SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
   FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"
```

```
Table          Size
orders         45 GB    # ⚠️ PROBLEM → 45GB table with no index = full scan = slow
payments       12 GB
users          200 MB   # ✅ small enough to be fast without index
```

### Fix

```bash
# Add index on the column used in WHERE clause
kubectl exec -it postgres-0 -n database -- \
  psql -U appuser -d mydb -c \
  "CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);"
# CONCURRENTLY means it builds the index without locking the table

# After index: same query goes from 8234ms → 3ms
```

---

## N+1 Query Problem

### What Is Happening?

Instead of getting all data in 1 query, the code runs 1 query to get a list, then runs 1 more query **for each item** in the list. 100 orders = 101 queries. Very slow.

### Sample — New Relic APM

```
APM → Transactions → GET /api/orders/history

Transaction breakdown:
  Total duration: 4,500ms
  Database calls: 101             # ⚠️ PROBLEM → should be 1 or 2 calls, not 101
  App code time:  50ms
  DB time:        4,450ms         # ⚠️ PROBLEM → almost all time spent in database

Queries run:
  SELECT * FROM orders WHERE user_id=9876  ← 1 query (gets 100 orders)
  SELECT * FROM products WHERE id=1        ← 1 query per order (100 more)
  SELECT * FROM products WHERE id=2
  SELECT * FROM products WHERE id=3
  ... (100 total product queries)          # ⚠️ PROBLEM → N+1 pattern
```

### Fix

```
Before (N+1 — bad):
  orders = db.query("SELECT * FROM orders WHERE user_id = ?", userId)
  for each order:
    order.product = db.query("SELECT * FROM products WHERE id = ?", order.productId)

After (1 query — good):
  orders = db.query("
    SELECT o.*, p.*
    FROM orders o
    JOIN products p ON o.product_id = p.id
    WHERE o.user_id = ?
  ", userId)
  ← One query, gets everything → 10ms instead of 4500ms
```

---

## Memory Leak (Gets Slower Every Day)

### What Is Happening?

The app creates things in memory (objects, connections, data) but never releases them. Over days, memory fills up and the app slows down until it eventually crashes (OOMKilled) and restarts.

### Sample — New Relic Infrastructure

```
Container Memory Usage (last 7 days):

Day 1:  ████░░░░░░  200MB / 512MB limit    # ✅ Normal
Day 2:  █████░░░░░  280MB / 512MB limit
Day 3:  ██████░░░░  340MB / 512MB limit
Day 5:  ████████░░  450MB / 512MB limit    # ⚠️ PROBLEM → keeps going up, never comes down
Day 7:  ██████████  512MB / 512MB limit → OOMKilled → pod restarts → starts at 200MB again
```

```bash
$ kubectl describe pod payment-xxx -n production
```
```
Last State: Terminated
  Reason:    OOMKilled              # ⚠️ PROBLEM → out of memory
  Exit Code: 137
  Started:   7 days ago
  Finished:  just now
# 💡 MEANS → pod ran for 7 days, memory grew every day, finally OOMKilled
```

### Diagnose

```bash
# Step 1 — New Relic → Infrastructure → Container
# Select your container → Memory chart → Does it only go up? Never comes down?
# That is the memory leak pattern

# Step 2 — Check pod uptime vs memory
kubectl top pods -n production
# High memory + recent restart (low AGE) = OOMKill from memory leak

# Step 3 — Correlate memory growth with specific endpoint
# APM → Transactions → which endpoint is called most often?
# Memory leak often tied to a specific code path called frequently
```

### Fix

```
Immediate fix: Increase memory limit to buy time
  kubectl set resources deployment payment -n production --limits=memory=1Gi

Real fix: Find the leak in code
  - Use APM profiling to find which objects grow unbounded
  - Common causes:
    * List/array that grows but never cleared
    * Event listeners added but never removed
    * Cache with no eviction policy
    * DB connections opened but not closed
```

---

## Cold Start Slowness (After New Pods Start)

### What Is Happening?

When new pods start (after scaling up or a deployment), the first few requests are slow because:
- JVM (Java) needs to warm up
- Caches are empty (first request fetches everything from DB)
- Connection pools are being established

### Sample — In New Relic

```
APM → Response Time chart

10:00 - 10:05   Average: 200ms    ← ✅ normal
10:05 - 10:06   Average: 3,200ms  ← ⚠️ PROBLEM → spike!
                                   # HPA added 3 new pods at 10:05
                                   # First requests to new pods are slow
10:06 - 10:10   Average: 210ms    ← ✅ back to normal (pods warmed up)

# 💡 MEANS → cold start only affects the first few requests per new pod
```

### Fix

```yaml
# Kubernetes fix: Readiness probe to delay traffic until pod is warm
readinessProbe:
  httpGet:
    path: /warmup    ← add a /warmup endpoint in your app
    port: 8080
  initialDelaySeconds: 60     ← wait 60s before sending any traffic
  periodSeconds: 10

# App fix: Pre-warm the cache on startup
# In your main() or @PostConstruct:
# cacheService.preloadHotData()   ← load most common data into cache before accepting requests
```

---

## Cascading Slowness (One Slow Service Slows Everything)

### What Is Happening?

Your app calls multiple services in a chain. If one service in the chain is slow, every request that passes through it is slow — like a slow lane on a highway backing up all traffic behind it.

### Sample — New Relic Distributed Tracing

```
Click on a slow request (4.2 seconds total):

Trace Waterfall:
  payment-service.handlePayment       3ms    ← ✅ fast
  ├── auth-service.validateToken      5ms    ← ✅ fast
  ├── fraud-service.checkFraud        8ms    ← ✅ fast
  ├── bank-api.verifyCard          4,100ms   ← ⚠️ PROBLEM → bank API taking 4 seconds!
  └── db.savePaymentRecord             4ms   ← ✅ fast

Total: 4,120ms
Root cause: bank-api.verifyCard   ← this one slow call makes everything slow
```

### Fix

```
Step 1 — Add timeout to bank API call
  httpClient.call(bankApiUrl, timeout=2000)  ← fail after 2 seconds instead of waiting 4s

Step 2 — Make it async where possible
  Submit payment for verification (don't wait for bank response)
  Bank calls your webhook when verified
  User gets "payment received, processing" instead of waiting

Step 3 — Add circuit breaker
  If bank API is slow 10 times in a row → stop calling it → fail fast → 503
  Better to fail fast than let 1000 users wait 4 seconds each
```

---

# PART 3 — EKS-Specific Issues

---

## Node Group Scaling Delay (3-5 Min Outage During Spikes)

### What Is Happening?

When traffic spikes suddenly (game event, flash sale), HPA creates new pods but there are no nodes to put them on. Cluster Autoscaler asks AWS for new EC2 nodes. New nodes take 3-5 minutes to join. During this time, new pods sit in `Pending` state and users get errors.

### Sample

```bash
$ kubectl get pods -n production
```
```
NAME                    READY   STATUS    AGE
payment-xxx-aaa         1/1     Running   2d
payment-xxx-bbb         1/1     Running   2d
payment-xxx-ccc         0/1     Pending   2m    # ⚠️ PROBLEM → waiting for a node
payment-xxx-ddd         0/1     Pending   2m    # ⚠️ PROBLEM
payment-xxx-eee         0/1     Pending   2m    # ⚠️ PROBLEM
```

```bash
$ kubectl describe pod payment-xxx-ccc -n production
```
```
Events:
  Warning  FailedScheduling  2m  scheduler
           0/4 nodes are available: 4 Insufficient cpu.
           # New nodes are being provisioned by Cluster Autoscaler...
           # ETA: 3-5 minutes before they join
```

### Fix

```yaml
# Keep warm spare capacity (always have 2 extra nodes ready)
# In AWS EKS node group settings:
#   Minimum size: current minimum + 2
#   Or use a dedicated "warm pool" in ASG

# For predictable events (game launch at 8 PM):
# Pre-scale manually 30 minutes before:
kubectl scale deployment payment -n production --replicas=20
# Cluster Autoscaler will add nodes proactively

# Long-term: Use Karpenter instead of Cluster Autoscaler
# Karpenter provisions nodes in ~60 seconds (vs 3-5 min)
```

---

## ALB Dropping Requests During Deployment

### What Is Happening?

During a rolling deployment, old pods are removed from the ALB target group. There is a delay (deregistration delay) between Kubernetes killing the pod and ALB stopping to send it traffic. During this delay, ALB sends requests to a pod that is already shutting down → 502 errors.

### Sample

```
During deployment at 14:30:
  14:30:00 - 14:30:30  Error rate: 0%    ← normal
  14:30:30 - 14:31:00  Error rate: 35%   ← ⚠️ PROBLEM → pod shutting down but ALB still sending traffic
  14:31:00 onwards     Error rate: 0%    ← normal

ALB Access Log during the spike:
  14:30:45  POST /api/payment  502  target: 10.0.1.45:8080
                                    error_reason: Target.NotInService
                                    # ⚠️ PROBLEM → pod removed from ECS but ALB didn't know yet
```

### Fix

```yaml
# Add preStop hook — pod waits before shutting down
# This gives ALB time to stop routing traffic to it
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 30"]
      # 30 seconds = longer than ALB deregistration delay (default 30s)

# Also set terminationGracePeriodSeconds to be longer than preStop + request time
terminationGracePeriodSeconds: 60
```

---

## RDS Connection Exhaustion

### What Is Happening?

Each pod maintains a pool of database connections. With many pods, the total connections exceed what RDS can handle. New pods cannot connect. Queries start failing.

### Sample

```bash
$ kubectl logs payment-xxx -n production
```
```
2026-04-12 12:00:00 ERROR  HikariPool-1 - Connection is not available,
                           request timed out after 30000ms
                           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                           # ⚠️ PROBLEM → cannot get a DB connection after 30 seconds
```

```bash
# Check total connections from database side
kubectl exec postgres-0 -n database -- \
  psql -U admin -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```
```
count   state
510     active     # ⚠️ PROBLEM → 510 active connections
0       idle
# RDS max_connections = 510 → completely full → new connections rejected
```

### Fix

```
Immediate:
  Reduce connection pool size per pod
  kubectl edit configmap db-config -n production
  Change: DB_POOL_SIZE=20 → DB_POOL_SIZE=5

Proper fix:
  Use RDS Proxy (AWS managed connection pooler)
  → 50 pods × 20 connections = 1000 "connections" to RDS Proxy
  → RDS Proxy maintains 50 real connections to RDS
  → Multiplexes efficiently
  → RDS never gets overwhelmed
```

---

## IAM / IRSA Token Expiry

### What Is Happening?

Pods on EKS use IAM Roles (IRSA) to access AWS services like S3, SQS, DynamoDB. These tokens auto-refresh every hour. If the refresh fails (network issue, IMDS unavailable), the pod loses AWS access and all S3/SQS calls fail.

### Sample

```bash
$ kubectl logs receipt-generator-xxx -n production
```
```
2026-04-12 13:00:00 ERROR  An error occurred (ExpiredTokenException)
                           when calling the PutObject operation:
                           The security token included in the request is expired.  # ⚠️ PROBLEM
                           Token expiry: 2026-04-12T12:59:30Z
                           Current time: 2026-04-12T13:00:00Z
                           # 💡 MEANS → pod's AWS credentials expired 30 seconds ago
                           # Auto-refresh failed silently
```

### Diagnose

```bash
# Check if pod can access AWS at all
kubectl exec receipt-generator-xxx -n production -- \
  aws sts get-caller-identity
# If this fails → IAM/IRSA broken

# Check if IMDS (metadata service) is accessible from pod
kubectl exec receipt-generator-xxx -n production -- \
  curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### Fix

```bash
# Restart the pod — it will get fresh credentials on start
kubectl rollout restart deployment receipt-generator -n production

# If it keeps happening → check IRSA setup
# Ensure pod's ServiceAccount has correct annotation:
kubectl describe serviceaccount receipt-sa -n production
# Should show: eks.amazonaws.com/role-arn: arn:aws:iam::xxx:role/receipt-role
```

---

# PART 4 — Payment-Specific Issues

---

## Double Payment (Idempotency Missing)

### What Is Happening?

User clicks "Pay". Network is slow, request seems to hang. User clicks "Pay" again. Both requests reach the server. Payment is charged twice.

### Sample — Database Evidence

```bash
$ kubectl exec postgres-0 -n database -- \
  psql -U appuser -d mydb -c \
  "SELECT user_id, amount, created_at FROM payments WHERE user_id=9876 ORDER BY created_at;"
```
```
user_id  amount    created_at
9876     1000.00   2026-04-12 14:00:01.234   ← first payment
9876     1000.00   2026-04-12 14:00:01.891   ← ⚠️ PROBLEM → second payment, 0.6 seconds later
                                               # Same user, same amount, 600ms apart = double charge
```

### Sample — App Logs

```bash
$ kubectl logs payment-service-xxx -n production
```
```
14:00:01.234  INFO   Processing payment for user 9876, amount 1000.00, requestId: abc-111
14:00:01.891  INFO   Processing payment for user 9876, amount 1000.00, requestId: abc-222
              ↑↑↑↑↑
              # ⚠️ PROBLEM → two different requestIds for same payment within 600ms
              # Idempotency key not used → both processed as separate payments
```

### Fix

```
Use Idempotency Keys:
  Frontend generates a unique key before sending payment: idempotencyKey = UUID()
  Backend stores this key with the payment
  If same key comes again → return the SAME result without charging again

Database change:
  ALTER TABLE payments ADD COLUMN idempotency_key VARCHAR(36) UNIQUE;
  INSERT INTO payments (user_id, amount, idempotency_key)
  VALUES (9876, 1000.00, 'abc-unique-key-123')
  ON CONFLICT (idempotency_key) DO NOTHING;   ← second request is ignored
```

---

## Payment Webhook Missed

### What Is Happening?

Payment gateways (Stripe, Razorpay) send a "payment confirmed" webhook to your app after charging the card. If your pod was restarting at that exact moment, the webhook is missed. Payment is confirmed in Stripe but your app never knows — order not placed, user paid but got nothing.

### Sample — Missing Webhook Evidence

```bash
$ kubectl logs payment-service-xxx -n production
```
```
14:10:00 INFO   Pod starting up...
14:10:15 INFO   Payment service ready
# ⚠️ PROBLEM → Stripe sent webhook at 14:10:08 during pod restart
#               No pod was ready to receive it
#               Stripe retried 3 times, all missed → gave up
```

```
Stripe Dashboard:
  Webhook delivery attempt 1: 14:10:08  Failed (no response)
  Webhook delivery attempt 2: 14:10:38  Failed (connection refused)
  Webhook delivery attempt 3: 14:11:08  Failed (connection refused)
  Status: Failed ← ⚠️ PROBLEM → payment confirmed in Stripe, not in your DB
```

### Fix

```yaml
# Fix 1 — Always have at least 2 replicas for webhook endpoint
# So when one pod restarts, the other handles the webhook
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0   ← never take all pods down at once

# Fix 2 — Poll payment status as backup (don't rely only on webhook)
# Every 5 minutes, check Stripe for any unconfirmed payments in your DB
# If Stripe says paid but your DB says pending → process it
```

---

## Circuit Breaker Open

### What Is Happening?

When a downstream service (bank API, fraud check) fails repeatedly, a circuit breaker "opens" — it stops sending requests to that service and immediately returns an error. This protects your app from wasting time on doomed requests, but users get instant errors instead of slow ones.

### Sample — App Logs

```bash
$ kubectl logs payment-service-xxx -n production
```
```
14:20:00 ERROR  BankAPI call failed (attempt 1/3)
14:20:02 ERROR  BankAPI call failed (attempt 2/3)
14:20:04 ERROR  BankAPI call failed (attempt 3/3)
14:20:04 WARN   Circuit breaker OPENED for BankAPI     # ← circuit breaker triggered
14:20:05 WARN   Circuit breaker OPEN — rejecting request immediately without calling BankAPI
14:20:05 WARN   Circuit breaker OPEN — rejecting request immediately without calling BankAPI
...
# ⚠️ PROBLEM → all payments failing instantly (no delay, just immediate failure)
# 💡 MEANS  → circuit breaker is protecting the system from the broken BankAPI
```

### Diagnose

```bash
# Check if the circuit breaker is due to a real downstream issue
curl -v https://api.bankname.com/health
# If this is down → circuit breaker is correct, bank API is broken

# Check circuit breaker metrics in New Relic
# APM → Custom → CircuitBreaker.state (if instrumented)
```

### Fix

```
Step 1 — Fix the underlying issue (bank API is down → contact bank, wait)
Step 2 — Circuit breaker will auto-close after the bank API recovers
Step 3 — For degraded mode: when bank API is down, show "payment processing delayed"
          instead of "payment failed" — better user experience
```

---

# PART 5 — Game-Specific Issues

---

## Thundering Herd (Everyone Hits at Same Time)

### What Is Happening?

Game event ends at exactly 10:00 PM. 100,000 players refresh leaderboard at the same second. All 100,000 requests hit the database simultaneously. Database collapses. Everyone gets errors.

### Sample

```bash
$ kubectl logs leaderboard-service-xxx -n production
```
```
22:00:00.000 INFO  Received 50,000 concurrent requests for leaderboard   # ⚠️ PROBLEM
22:00:00.001 ERROR Connection pool exhausted
22:00:00.001 ERROR Connection pool exhausted
... (50,000 lines of errors)
22:00:30 ERROR Database CPU: 100%, all queries timing out                # ⚠️ PROBLEM
```

```
New Relic dashboard at 22:00:00:
  Throughput:     0 → 50,000 req/s    ← instant spike
  Response time:  200ms → 45,000ms   ← ⚠️ PROBLEM → 45 seconds!
  Error rate:     0% → 99%           ← ⚠️ PROBLEM → almost everyone failed
```

### Fix

```bash
# Fix: Cache the leaderboard in Redis — update every 30 seconds
# Instead of hitting DB for every request:
# All 100,000 users read from Redis cache → 1ms response
# Background job updates Redis from DB every 30 seconds

# Fix: Stagger the refresh — add a small random delay per user
# Instead of all refreshing at exactly 22:00:00:
# Each client refreshes at 22:00:00 + random(0, 5 seconds)
# Load is spread over 5 seconds instead of 1 millisecond
```

---

## Retry Storm

### What Is Happening?

Service is slow → clients retry → more load → service gets slower → more retries → complete collapse. Like 1000 people calling the same customer service number when the lines are busy. More calls make it worse.

### Sample — New Relic

```
APM → Throughput chart:

Normal:       500 req/min
Problem:    5,000 req/min  (10x spike)

But unique users: still 500
→ ⚠️ PROBLEM → each user retried ~10 times automatically
→ 500 users × 10 retries = 5,000 requests
→ Extra load makes the service even slower
→ Users retry even more → death spiral
```

### Fix

```
Use Exponential Backoff with Jitter:

First retry:  wait 1 second
Second retry: wait 2 seconds
Third retry:  wait 4 seconds + random(0, 1 second)   ← jitter prevents synchronized retries
Fourth retry: wait 8 seconds
Maximum wait: 30 seconds, then give up

This ensures retries don't all happen at the same time
and the load reduces as more retries are delayed.
```

---

## Cache Stampede

### What Is Happening?

A popular item is cached in Redis. When the cache expires, 1000 requests all try to rebuild it at the same time (all hitting the database). Database gets overwhelmed for a few seconds. Then cache is rebuilt and everything is fine again. Happens repeatedly every time cache expires.

### Sample — Log Pattern

```bash
$ kubectl logs game-service-xxx -n production
```
```
15:30:00.000 INFO   Cache miss for leaderboard:global:page1    # ← cache expired
15:30:00.001 INFO   Cache miss for leaderboard:global:page1    # ⚠️ PROBLEM
15:30:00.002 INFO   Cache miss for leaderboard:global:page1    # ⚠️ PROBLEM
... (1000 cache misses in 1 millisecond)
15:30:00.003 ERROR  Database connection pool exhausted          # ⚠️ PROBLEM → 1000 DB queries at once
15:30:02.150 INFO   Cache set for leaderboard:global:page1     # cache rebuilt
15:30:02.151 INFO   Cache hit for leaderboard:global:page1     # ✅ back to normal
```

### Fix

```
Probabilistic Early Expiry:
  Before cache expires, a few requests start rebuilding it
  Most requests still get the cached value
  Cache is always fresh, never a hard miss for all users

Mutex Lock:
  When cache misses → only 1 request rebuilds the cache
  All other requests wait for that 1 request to finish
  Then everyone reads from cache → DB only hit once, not 1000 times
```

---

## SSL Certificate Expiry

### What Is Happening?

SSL certificates have an expiry date. If no one renews them, the certificate expires and users get "Your connection is not private" error. All HTTPS traffic stops working.

### Sample — What Users See

```
Browser shows:
  ⚠️ Your connection is not private
  NET::ERR_CERT_DATE_INVALID
  The certificate for payment.devopscab.com expired on April 10, 2026   # ⚠️ PROBLEM
```

### Sample — AWS Certificate Manager (ACM)

```
AWS Console → Certificate Manager:
  payment.devopscab.com   Status: EXPIRED    Expiry: 2026-04-10   # ⚠️ PROBLEM
  api.devopscab.com       Status: Issued     Expiry: 2027-01-15   # ✅ HEALTHY
```

### Fix

```bash
# Immediate fix — request new certificate in ACM
aws acm request-certificate \
  --domain-name payment.devopscab.com \
  --validation-method DNS

# Then attach new certificate to your ALB

# Prevention — use ACM managed certificates (auto-renew)
# Or use cert-manager in Kubernetes (auto-renews Let's Encrypt certs)

# Set up New Relic alert for expiry:
# Query: SELECT daysUntilExpiry FROM SslCertificate WHERE hostname = 'payment.devopscab.com'
# Alert when: daysUntilExpiry < 30
```

---

# Summary — All Issues at a Glance

## HTTP Errors

| Code | Name | Most Common Cause | First Place to Look |
|---|---|---|---|
| 400 | Bad Request | Wrong data format from frontend | APM → Errors → request body |
| 401 | Unauthorized | JWT expired, not logged in | APM → Errors → auth service logs |
| 403 | Forbidden | Wrong role, missing IAM permission | App logs → "Access denied" message |
| 404 | Not Found | Wrong URL, pod scaled to 0, ingress missing path | `kubectl get pods` + `kubectl get endpoints` |
| 408 | Request Timeout | Large upload, slow client connection | ALB access logs → request_processing_time |
| 429 | Too Many Requests | Rate limiter hit, external API limit | APM → Throughput → req/s count |
| 500 | Server Error | Code crash, null pointer, unhandled exception | APM → Errors → full stack trace |
| 502 | Bad Gateway | Pod not ready, wrong port, pod crashing | `kubectl get pods` → READY column |
| 503 | Service Unavailable | All pods down, DB pool full | `kubectl get pods` + `kubectl get endpoints` |
| 504 | Gateway Timeout | Slow DB query, slow external API, CPU throttle | APM → Distributed Tracing → find slow span |

## Slowness Issues

| Issue | Signature | First Check |
|---|---|---|
| Slow DB query | High latency + 0% error | APM → Databases → slowest queries |
| N+1 queries | 100+ DB calls per request | APM → Transaction trace → DB call count |
| Memory leak | Latency grows daily, OOMKill every N days | Infra → Container memory → trending up |
| Cold start | Spike after new pods start | APM → Response time correlated with deployment |
| Cascading slowness | One service makes all slow | APM → Distributed Tracing → find slow span |

## EKS-Specific

| Issue | Signature | Fix |
|---|---|---|
| Node scaling delay | Pods Pending for 3-5 min during spike | Pre-scale, warm nodes, use Karpenter |
| ALB drop on deploy | 502 spikes for 30s during rollout | Add preStop hook with sleep 30 |
| RDS connections full | 503 + "pool exhausted" in logs | Use RDS Proxy |
| IAM token expiry | AWS calls fail with ExpiredToken | Restart pod, fix IRSA annotation |

## Payment / Game

| Issue | Signature | Fix |
|---|---|---|
| Double payment | Same user charged twice | Use idempotency keys |
| Webhook missed | Stripe paid, order not placed | Multiple replicas, poll as backup |
| Circuit breaker open | Instant errors, 0ms response | Fix downstream service |
| Thundering herd | Sudden 503 at exact event time | Cache + rate limit + stagger requests |
| Retry storm | Throughput 10x but unique users same | Exponential backoff with jitter |
| Cache stampede | Short 503 spikes periodically | Mutex lock or probabilistic expiry |
| SSL expired | Users see "connection not private" | ACM auto-renew or cert-manager |

---

*Last updated: April 2026 | Cluster: kind-calico-prod | Read alongside: K8s_issues.md, K8s_issues_samples.md, K8s_missing_issues.md*
