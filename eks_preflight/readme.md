# EKS Upgrade Preflight Guardrail (V1)

A CLI-based preflight validation tool to prevent common failure scenarios during **Amazon EKS worker node upgrades**.

## Problem Statement

During an EKS worker node upgrade, workloads started failing with:

* CNI unable to allocate IP address
* IP exhaustion in worker subnets
* CNI conflicts (AWS VPC CNI + Calico)
* Add-on version inconsistencies

### Root Cause

Subnet IP exhaustion during node replacement combined with runtime configuration gaps.

This tool was built to convert that production incident into a **deterministic preflight guardrail**.

It checks cluster state before upgrade and answers one simple question:

> **Is it safe to upgrade?**

---

## What This Tool Checks (V1)

### 1️⃣ Subnet IP Capacity

* Detects available IPs per subnet
* Calculates required IPs using:

  * Live `maxPods` from Kubernetes node (if available)
  * Fallback ENI-based calculation
* Prevents subnet exhaustion during rolling upgrades

---

### 2️⃣ CNI Conflict Detection

* Detects coexistence of:
  * AWS VPC CNI
  * Calico
* Flags potential dual IPAM scenarios

### 3️⃣ Add-on Visibility

Lists presence of:

* `kube-proxy`
* `coredns`
* `vpc-cni`

Marks compatibility as **manual review (V1)**.

---

### 4️⃣ Deterministic Final Verdict

Outputs one of:

```
SAFE TO UPGRADE
NOT SAFE TO UPGRADE
```

---

### 5️⃣ CI/CD Ready

Exit codes:

* `Exit Code 0` → Safe
* `Exit Code 2` → Unsafe

Perfect for pipeline integration (Jenkins / GitHub Actions).

---

## 🛠 Architecture Flow

High-level execution flow:

1. Parse CLI arguments
2. Create AWS session
3. Fetch EKS node group metadata
4. Detect live `maxPods` from cluster
5. Calculate required IPs
6. Compare with subnet available IPs
7. Check CNI coexistence
8. Check add-on presence
9. Produce final upgrade verdict

---

## 🖥 Example Usage

```bash
python main.py \
  --cluster wonderful-jazz-ant \
  --region ap-south-1 \
  --nodegroup wonderful-jazz-ant-managed-ng
```

---

## 📄 Example Output

```
Cluster Name : wonderful-jazz-ant
Region       : ap-south-1
Cluster Type : eks

Fetching node group details...

Node Group Info:
  Subnets       : ['subnet-09b8de905df15fa44', 'subnet-0a149f0dd615da7c7']
  InstanceTypes : ['t3.medium']
  Desired Size  : 1

Live maxPods detected from node: 17

Checking subnet IP availability...

Instance Type          : t3.medium
Max Pods per Node      : 17
Nodes Being Replaced   : 1
Required IPs per Subnet: 17

  Subnet subnet-09b8de905df15fa44 has only 4 IPs (required 17)
  Subnet subnet-0a149f0dd615da7c7 has only 10 IPs (required 17)

Running CNI conflict check...

CNI check: PASSED

Running Add-on compatibility check...

Add-on check: REVIEW (Version compatibility not strictly validated in v1)

================ FINAL RESULT ================

NOT SAFE TO UPGRADE
```

---

## 🎯 Why This Matters

Instead of discovering failures during a live upgrade:

* ❌ No pod crashes
* ❌ No CNI panic
* ❌ No emergency subnet expansion
* ❌ No firefighting

The system validates safety **before touching production**.

This converts operational pain into repeatable engineering logic.

---

## 📦 Tech Stack

* Python
* boto3 (AWS SDK)
* Kubernetes Python Client
* Modular CLI Architecture
* Exit-code driven validation

---

## 🧭 Roadmap (Future Enhancements)

* Strict add-on version compatibility validation
* Multi-nodegroup scanning
* JSON output mode for CI pipelines
* Logging + structured reporting
* Support for ECS clusters

---

## 👤 Author

Built by a DevOps Engineer transitioning toward platform architecture by turning real production incidents into engineering guardrails.