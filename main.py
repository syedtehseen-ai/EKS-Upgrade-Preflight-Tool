import json
import sys
import boto3
from kubernetes import client as k8s_client, config as k8s_config

SUPPORTED_CLUSTER_TYPES = ["eks"]
INSTANCE_LIMITS = { # later this can be done dynamically
    "t3.medium": {"enis": 3, "ips_per_eni": 6},
    "m5.large": {"enis": 3, "ips_per_eni": 10}
}

def create_aws_session(region, role_arn=None):
    if role_arn:
        sts = boto3.client("sts", region_name=region)
        resp = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="eks-upgrade-preflight"
        )

        creds = resp["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region
        )

    return boto3.Session(region_name=region)

def calculate_max_pods(instance_type):
    limits = INSTANCE_LIMITS.get(instance_type)

    if not limits:
        print(f"WARNING: Unknown instance type {instance_type}, defaulting max pods to 20")
        return 20

    return (limits["enis"] * limits["ips_per_eni"]) - 1

def get_live_max_pods(node_group_name, v1):
    try:
        # k8s_config.load_kube_config()
        # v1 = k8s_client.CoreV1Api()

        nodes = v1.list_node()

        for node in nodes.items:
            labels = node.metadata.labels or {}

            if labels.get("eks.amazonaws.com/nodegroup") == node_group_name:
                allocatable = node.status.allocatable
                max_pods = int(allocatable.get("pods"))
                print(f"Live maxPods detected from node: {max_pods}")
                return max_pods

    except Exception as e:
        print(f"Could not detect live maxPods: {e}")

    return None
##### CNI Compatibility #######

def check_cni_conflict(v1):
    try:
        # k8s_config.load_kube_config()
        # apps = k8s_client.AppsV1Api()

        daemonsets = v1.list_namespaced_daemon_set(namespace="kube-system")
        aws_cni = False
        calico = False
        for ds in daemonsets.items:
            name = ds.metadata.name

            if name == "aws-node":
                aws_cni = True
            if "calico" in name:
                calico = True

        if aws_cni and calico:
            print("CNI CONFLICT: AWS VPC CNI and Calico both detected")
            return False
        print("CNI check: PASSED")
        return True

    except Exception as e:
        print(f"CNI check failed to execute: {e}")
        return False

def check_addon_compatibility(session, cluster_name):
    try:
        eks = session.client("eks")

        cluster_info = eks.describe_cluster(name=cluster_name)
        cluster_version = cluster_info["cluster"]["version"]

        addons = ["kube-proxy", "coredns", "vpc-cni"]

        incompatible = False

        for addon in addons:
            try:
                addon_info = eks.describe_addon(
                    clusterName=cluster_name,
                    addonName=addon
                )
                addon_version = addon_info["addon"]["addonVersion"]
                print(f"{addon}: {addon_version}")

            except Exception:
                print(f"{addon}: Not installed or unmanaged")

        print("Addon compatibility check: REVIEW MANUALLY (v1 logic)") # later this can be done dynamically
        return True

    except Exception as e:
        print(f"Addon compatibility check failed: {e}")
        return False

def main():
    try:
        with open("input.json", "r") as f:
            data = json.load(f)

        cluster_name = data.get("cluster_name")
        region = data.get("region")
        cluster_type = data.get("cluster_type")
        role_arn = data.get("assume_role_arn")
        node_group_name = data.get("node_group_name")

        if not cluster_name or not region or not cluster_type:
            print("ERROR: cluster_name, region, or cluster_type missing")
            sys.exit(1)

        print("Cluster Name:", cluster_name)
        print("Region:", region)
        print("Cluster Type:", cluster_type)
        print("Input validation: PASSED")
        
        session = create_aws_session(region, role_arn)

        sts = session.client("sts")
        eks = session.client("eks")
        ec2 = session.client("ec2")

        # Load kube config ONCE
        k8s_config.load_kube_config()
        # Create API client ONCE
        v1 = k8s_client.CoreV1Api()

        # Pass client to functions
        get_live_max_pods(node_group_name, v1)
        check_cni_conflict(v1)

        identity = sts.get_caller_identity()
        print("AWS Identity:", identity["Arn"])

        # Node Describing                
        print("\nFetching node group details...\n")

        response = eks.describe_nodegroup(
            clusterName=cluster_name,
            nodegroupName=node_group_name#what if there are multiple node groups -- To-do V2
        )
        nodegroup = response["nodegroup"]
        subnets = nodegroup.get("subnets", [])
        instance_types = nodegroup.get("instanceTypes", [])
        desired_size = nodegroup.get("scalingConfig", {}).get("desiredSize")

        print("Node Group Info:")
        print("Subnets:", subnets)
        print("Instance Types:", instance_types)
        print("Desired Size:", desired_size)
        print("\ndescribe_nodegroup: PASSED")


        # Subnet Describing 
        print("\nChecking subnet IP availability...\n")

        if not instance_types:
            print("ERROR: No instance type found in nodegroup")
            sys.exit(1)
        instance_type = instance_types[0]
        live_max_pods = get_live_max_pods(node_group_name, v1)

        if live_max_pods:
            max_pods = live_max_pods
        else:
            max_pods = calculate_max_pods(instance_type)
            print(f"Using ENI math fallback maxPods: {max_pods}")


        nodes_being_replaced = desired_size
        required_ips = max_pods * nodes_being_replaced
        print(f"Instance Type: {instance_type}")
        print(f"Max Pods per Node: {max_pods}")
        print(f"Nodes Being Replaced: {nodes_being_replaced}")
        print(f"Required IPs per Subnet: {required_ips}\n")
        upgrade_safe = True

        for subnet_id in subnets:
            subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
            subnet_info = subnet_response["Subnets"][0]
            available_ips = subnet_info["AvailableIpAddressCount"]

            if available_ips < required_ips:
                print(f" Subnet {subnet_id} has only {available_ips} IPs (required {required_ips})")
                upgrade_safe = False
            else:
                print(f" Subnet {subnet_id} is safe")

        print("\nRunning CNI conflict check...\n")
        cni_safe = check_cni_conflict(v1)

        print("\nRunning Add-on compatibility check...\n")
        addon_safe = check_addon_compatibility(session, cluster_name)

        overall_safe = upgrade_safe and cni_safe and addon_safe

        print("\n================ FINAL RESULT ================\n")

        if overall_safe:
            print(" SAFE TO UPGRADE")
            sys.exit(0)
        else:
            print("NOT SAFE TO UPGRADE")
            sys.exit(2)




    except FileNotFoundError:
        print("ERROR: input.json not found")
        sys.exit(1)

    except json.JSONDecodeError:
        print("ERROR: input.json is not valid JSON")
        sys.exit(1)

if __name__ == "__main__":
    main()