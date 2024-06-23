from kubernetes import client, config
import random
import string

def generate_pod_name():
    return 'worker-' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

def k8s_create_node(image_name):
    # Load the Kubernetes configuration
    try:
        # Load the in-cluster configuration
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    # Define the pod spec
    pod_name = generate_pod_name()
    pod = client.V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=client.V1ObjectMeta(name=pod_name),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="ubuntu",
                    image=image_name,
                    image_pull_policy="IfNotPresent",
                    ports=[client.V1ContainerPort(container_port=22, name="ssh")],
                    security_context=client.V1SecurityContext(
                        capabilities=client.V1Capabilities(add=["SYS_ADMIN"])
                    )
                )
            ]
        )
    )

    # Create the pod
    v1 = client.CoreV1Api()
    v1.create_namespaced_pod(namespace="default", body=pod)

    # Wait for the pod to be running and get its IP address
    while True:
        pod_status = v1.read_namespaced_pod_status(name=pod_name, namespace="default")
        if pod_status.status.phase == "Running":
            pod_ip = pod_status.status.pod_ip
            return pod_ip

def k8s_destroy_node(server_ip):
    try:
        # Load the in-cluster configuration
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    # Get the list of pods
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace="default")

    # Find the pod with the given IP address and delete it
    for pod in pods.items:
        if pod.status.pod_ip == server_ip:
            v1.delete_namespaced_pod(name=pod.metadata.name, namespace="default")
            return f"Pod with IP {server_ip} deleted"

    return f"Pod with IP {server_ip} not found"


class K8SNodeController:
    def __init__(self, image_name):
        self.image_name = image_name

    def create(self):
        return k8s_create_node(self.image_name)

    def destroy(self, pod_ip):
        return k8s_destroy_node(pod_ip)
