import argparse
import sys

from aws_utils import create_aws_session
from k8s_utils import init_k8s_client, get_live_max_pods
from checks.cni import check_cni_conflict
from checks.addons import check_addon_compatibility


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
    core_v1, apps_v1 = init_k8s_client()

    # ---- Basic Info ----
    print("\nCluster Name :", args.cluster)
    print("Region       :", args.region)
    print("Cluster Type : eks\n")

    # ---- Fetch Nodegroup ----
    print("Fetching node group details...\n")

    response = eks.describe_nodegroup(
        clusterName=args.cluster,
        nodegroupName=args.nodegroup
    )

    nodegroup = response["nodegroup"]

    subnets = nodegroup.get("subnets", [])
    instance_types = nodegroup.get("instanceTypes", [])
    desired_size = nodegroup.get("scalingConfig", {}).get("desiredSize")

    print("Node Group Info:")
    print("  Subnets       :", subnets)
    print("  InstanceTypes :", instance_types)
    print("  Desired Size  :", desired_size)

    # ---- Max Pods ----
    live_max = get_live_max_pods(args.nodegroup, core_v1)

    if live_max:
        print(f"\nLive maxPods detected from node: {live_max}")
        max_pods = live_max
    else:
        print("\nLive maxPods could not be detected, using ENI fallback")
        max_pods = 20

    # ---- Subnet Capacity ----
    print("\nChecking subnet IP availability...\n")

    if not instance_types:
        print("ERROR: No instance type found")
        sys.exit(1)

    instance_type = instance_types[0]
    required_ips = max_pods * desired_size

    print("Instance Type          :", instance_type)
    print("Max Pods per Node      :", max_pods)
    print("Nodes Being Replaced   :", desired_size)
    print("Required IPs per Subnet:", required_ips)
    print()

    subnet_safe = True

    for subnet_id in subnets:
        subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
        available_ips = subnet_response["Subnets"][0]["AvailableIpAddressCount"]

        if available_ips < required_ips:
            print(f"  Subnet {subnet_id} has only {available_ips} IPs (required {required_ips})")
            subnet_safe = False
        else:
            print(f"  Subnet {subnet_id} OK ({available_ips} IPs available)")

    # ---- CNI Check ----
    print("\nRunning CNI conflict check...\n")

    cni_safe = check_cni_conflict(apps_v1)

    if cni_safe:
        print("CNI check: PASSED")
    else:
        print("CNI check: FAILED (Conflict detected)")

    # ---- Add-on Check ----
    print("\nRunning Add-on compatibility check...\n")

    addon_safe = check_addon_compatibility(session, args.cluster)

    if addon_safe:
        print("Add-on check: REVIEW (Version compatibility not strictly validated in v1)")
    else:
        print("Add-on check: FAILED")


    # ---- Final Result ----
    print("\n================ FINAL RESULT ================\n")

    overall_safe = subnet_safe and cni_safe and addon_safe

    if overall_safe:
        print("SAFE TO UPGRADE\n")
        sys.exit(0)
    else:
        print("NOT SAFE TO UPGRADE\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
