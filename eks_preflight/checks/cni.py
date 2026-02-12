def check_cni_conflict(apps_v1):
    daemonsets = apps_v1.list_namespaced_daemon_set(namespace="kube-system")

    aws_cni = False
    calico = False

    for ds in daemonsets.items:
        name = ds.metadata.name
        if name == "aws-node":
            aws_cni = True
        if "calico" in name:
            calico = True

    if aws_cni and calico:
        return False

    return True
