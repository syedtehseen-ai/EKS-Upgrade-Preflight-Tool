# EKS Upgrade Preflight Guardrail (V1.1)

A CLI-based preflight validation tool to prevent common failure scenarios during **Amazon EKS worker node upgrades**.

## Problem Statement

During an EKS worker node upgrade, workloads started failing with:

* CNI unable to allocate IP address
* IP exhaustion in worker subnets
* Too many pods on node -- new in v1.1
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

### 2️⃣ Instance Type Capacity (NEW 🔥)
- ENI + IP limits from AWS  
- Validates max pods per node  
- Detects **“Too many pods” issue**

### 3️⃣ CNI Conflict Detection

* Detects coexistence of:
  * AWS VPC CNI
  * Calico
* Flags potential dual IPAM scenarios

### 4️⃣ Add-on Visibility

Lists presence of:

* `kube-proxy`
* `coredns`
* `vpc-cni`

Marks compatibility as **manual review (V1)**.

---

### 5️⃣ Deterministic Final Verdict

Outputs one of:

```
SAFE TO UPGRADE
NOT SAFE TO UPGRADE
```
---

### 6️⃣ CI/CD Ready

Exit codes:

* `Exit Code 0` → Safe
* `Exit Code 2` → Unsafe

Perfect for pipeline integration (Jenkins / GitHub Actions).

---

##  Architecture Flow

High-level execution flow:

1. Parse CLI arguments
2. Create AWS session
3. Fetch EKS node group metadata
4. Detect live `maxPods` from cluster
5. Calculate required IPs
6. Compare with subnet available IPs
7. Validates max pods per node
7. Check CNI coexistence
8. Check add-on presence
9. Produce final upgrade verdict

---

##  Example Usage

## ⚙️ Installation
### 🔹 Option 1 — Step 01 - Install from GitHub

```bash
pip install git+https://github.com/syedtehseen-ai/EKS-Upgrade-Preflight-Tool.git
```
### step 02 - Usage
```bash
eks-preflight \
  --cluster wonderful-jazz-ant \
  --region ap-south-1 \
  --nodegroup wonderful-jazz-ant-managed-ng
```
⚠️ Note: Use eks-preflight (CLI command), not eks_preflight (Python package name).
##  Example Output

```
=== EKS Preflight Check ===

Cluster: deployguard-cluster-dev (ap-south-1)

[Node Group]
  Instance Type : t3.micro
  Desired Size  : 2
  Max Pods/Node : 4

[Instance Capacity]
  Supported Pods : 3
  Status         : ❌ FAIL (Insufficient capacity)
💡 Recommendation: Upgrade instance type Or reduce pod density per node


[Subnet Capacity]
  Required IPs per subnet : 8
  subnet-xxx : ✅ OK (246 available)
  subnet-yyy : ✅ OK (246 available)

[Checks]
  CNI Check        : ✅ PASS
  Add-on Check     : ⚠️ REVIEW

=== FINAL RESULT ===
❌ NOT SAFE TO UPGRADE
```
### 🔹 Option 2 — Local Development

```bash
git clone https://github.com/syedtehseen-ai/EKS-Upgrade-Preflight-Tool.git
cd EKS-Upgrade-Preflight-Tool
pip install -e .
```
---
---

##  Why This Matters

Instead of discovering failures during a live upgrade:

* ❌ No pod crashes
* ❌ No CNI panic
* ❌ No emergency subnet expansion
* ❌ No firefighting

The system validates safety **before touching production**.

This converts operational pain into repeatable engineering logic.

---

##  Tech Stack

* Python
* boto3 (AWS SDK)
* Kubernetes Python Client
* Modular CLI Architecture
* Exit-code driven validation

---

##  Roadmap (Future Enhancements)

* Strict add-on version compatibility validation
* Multi-nodegroup scanning
* JSON output mode for CI pipelines
* Logging + structured reporting
* Support for ECS clusters

---

##  Author


Built by a DevOps Engineer transitioning toward platform architecture by turning real production incidents into engineering guardrails..
  