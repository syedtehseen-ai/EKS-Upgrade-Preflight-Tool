import argparse
import sys

from eks_preflight.aws_utils import create_aws_session
from eks_preflight.k8s_utils import (
    init_k8s_client,
    get_live_max_pods,
    get_instance_network_limits
)
from eks_preflight.checks.cni import check_cni_conflict
from eks_preflight.checks.addons import check_addon_compatibility


def main():

    parser = argparse.ArgumentParser(description="EKS Upgrade Preflight Guardrail")
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--nodegroup", required=True)
    parser.add_argument("--role-arn", required=False)

    args = parser.parse_args()

    # ---- AWS Session ----
    session = create_aws_session(args.region, args.role_arn)
    eks = session.client("eks")
    ec2 = session.client("ec2")

    # ---- Kubernetes Clients ----
    core_v1, apps_v1 = init_k8s_client(args.cluster, args.region)

    # ---- Header ----
    print("\n=== EKS Preflight Check ===\n")
    print(f"Cluster: {args.cluster} ({args.region})\n")

    # ---- Fetch Nodegroup ----
    response = eks.describe_nodegroup(
        clusterName=args.cluster,
        nodegroupName=args.nodegroup
    )

    nodegroup = response["nodegroup"]

    subnets = nodegroup.get("subnets", [])
    instance_types = nodegroup.get("instanceTypes", [])
    desired_size = nodegroup.get("scalingConfig", {}).get("desiredSize")

    if not instance_types:
        print("ERROR: No instance type found")
        sys.exit(1)

    instance_type = instance_types[0]

    # ---- Max Pods ----
    live_max = get_live_max_pods(args.nodegroup, core_v1)

    if live_max:
        max_pods = live_max
    else:
        max_pods = 20  # fallback

    # ---- Node Group Info ----
    print("[Node Group]")
    print(f"  Instance Type : {instance_type}")
    print(f"  Desired Size  : {desired_size}")
    print(f"  Max Pods/Node : {max_pods}")

    # ---- Instance Capacity ----
    max_enis, ips_per_eni = get_instance_network_limits(instance_type, args.region)

    max_possible_ips = max_enis * ips_per_eni
    max_possible_pods = max_possible_ips - 1  # AWS reserves 1

    print("\n[Instance Capacity]")
    print(f"  Supported Pods : {max_possible_pods}")

    instance_safe = True
    if max_pods > max_possible_pods:
        print("  Status         : ❌ FAIL (Insufficient capacity)")
        print("💡 Recommendation: Upgrade instance type Or reduce pod density per node\n")
        instance_safe = False
    else:
        print("  Status         : ✅ PASS")

    # ---- Subnet Capacity ----
    required_ips = max_pods * desired_size

    print("\n[Subnet Capacity]")
    print(f"  Required IPs per subnet : {required_ips}")

    subnet_safe = True

    for subnet_id in subnets:
        subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
        available_ips = subnet_response["Subnets"][0]["AvailableIpAddressCount"]

        if available_ips < required_ips:
            print(f"  {subnet_id} : ❌ FAIL ({available_ips} available)")
            print("💡 Recommendation: Add more nodes/subnets OR Expand CIDR")
            subnet_safe = False
        else:
            print(f"  {subnet_id} : ✅ OK ({available_ips} available)")

    # ---- Checks ----
    print("\n[Checks]")

    cni_safe = check_cni_conflict(apps_v1)
    print(f"  CNI Check        : {'✅ PASS' if cni_safe else '❌ FAIL'}")

    addon_safe = check_addon_compatibility(session, args.cluster)
    print(f"  Add-on Check     : {'⚠️ REVIEW' if addon_safe else '❌ FAIL'}")

    # ---- Final Result ----
    print("\n=== FINAL RESULT ===")

    overall_safe = subnet_safe and cni_safe and addon_safe and instance_safe

    if overall_safe:
        print("✅ SAFE TO UPGRADE\n")
        sys.exit(0)
    else:
        print("❌ NOT SAFE TO UPGRADE\n")
        sys.exit(2)


if __name__ == "__main__":
    main()