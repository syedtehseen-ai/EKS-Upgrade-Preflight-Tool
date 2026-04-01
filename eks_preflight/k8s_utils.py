from kubernetes import client
import boto3
import base64
import subprocess
import json
import tempfile


def init_k8s_client(cluster_name, region):
    eks = boto3.client("eks", region_name=region)
    cluster = eks.describe_cluster(name=cluster_name)["cluster"]

    endpoint = cluster["endpoint"]
    ca_data = cluster["certificateAuthority"]["data"]

    # Get token
    token = subprocess.check_output(
        ["aws", "eks", "get-token", "--cluster-name", cluster_name, "--region", region]
    )
    token = json.loads(token)["status"]["token"]

    # Decode CA and write to file
    ca_cert = base64.b64decode(ca_data)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(ca_cert)
        ca_path = f.name

    # Configure client
    configuration = client.Configuration()
    configuration.host = endpoint
    configuration.verify_ssl = True
    configuration.ssl_ca_cert = ca_path   # ✅ FIX
    configuration.api_key = {"authorization": "Bearer " + token}

    client.Configuration.set_default(configuration)

    return client.CoreV1Api(), client.AppsV1Api()

def get_live_max_pods(node_group_name, core_v1):
    try:
        nodes = core_v1.list_node()

        for node in nodes.items:
            labels = node.metadata.labels or {}

            if labels.get("eks.amazonaws.com/nodegroup") == node_group_name:
                allocatable = node.status.allocatable
                return int(allocatable.get("pods"))

    except Exception:
        return None
def get_instance_network_limits(instance_type, region):
    ec2 = boto3.client("ec2", region_name=region)

    response = ec2.describe_instance_types(
        InstanceTypes=[instance_type]
    )

    info = response["InstanceTypes"][0]["NetworkInfo"]

    max_enis = info["MaximumNetworkInterfaces"]
    ips_per_eni = info["Ipv4AddressesPerInterface"]

    return max_enis, ips_per_eni
