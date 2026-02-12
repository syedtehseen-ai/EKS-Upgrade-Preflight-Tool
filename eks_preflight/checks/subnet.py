from constants import INSTANCE_LIMITS

def calculate_max_pods(instance_type):
    limits = INSTANCE_LIMITS.get(instance_type)

    if not limits:
        return 20

    return (limits["enis"] * limits["ips_per_eni"]) - 1


def check_subnet_capacity(ec2, subnets, instance_type, desired_size, live_max_pods=None):

    if live_max_pods:
        max_pods = live_max_pods
    else:
        max_pods = calculate_max_pods(instance_type)

    required_ips = max_pods * desired_size

    details = []
    upgrade_safe = True

    for subnet_id in subnets:
        subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
        subnet_info = subnet_response["Subnets"][0]
        available_ips = subnet_info["AvailableIpAddressCount"]

        details.append({
            "subnet": subnet_id,
            "available": available_ips
        })

        if available_ips < required_ips:
            upgrade_safe = False

    return {
        "safe": upgrade_safe,
        "required_ips": required_ips,
        "max_pods": max_pods,
        "details": details
    }

