SUPPORTED_CLUSTER_TYPES = ["eks"]

INSTANCE_LIMITS = {
    "t3.medium": {"enis": 3, "ips_per_eni": 6},
    "m5.large": {"enis": 3, "ips_per_eni": 10}
}
