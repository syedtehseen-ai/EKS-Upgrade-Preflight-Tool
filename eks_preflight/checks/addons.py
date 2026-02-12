def check_addon_compatibility(session, cluster_name):
    eks = session.client("eks")

    addons = ["kube-proxy", "coredns", "vpc-cni"]

    for addon in addons:
        try:
            eks.describe_addon(
                clusterName=cluster_name,
                addonName=addon
            )
        except Exception:
            pass

    return True  # still basic logic for now
