from kubernetes import client as k8s_client, config as k8s_config

def init_k8s_client():
    k8s_config.load_kube_config()
    core_v1 = k8s_client.CoreV1Api()
    apps_v1 = k8s_client.AppsV1Api()

    return core_v1, apps_v1

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
