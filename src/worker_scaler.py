import time
import string
import random
import urllib3

from datetime import datetime, timedelta
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from os import environ

from queue_watcher import QueueWatcher


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AutoScaler(object):
    def generate_random_id(self, size=12, chars=string.ascii_lowercase + string.digits):
        return "".join(random.choice(chars) for _ in range(size))

    def create_job_object(
        self,
        name,
        container_image,
        namespace,
        container_name,
        labels={},
    ):
        body = client.V1Job(api_version="batch/v1", kind="Job")
        # Each job must have a different name
        body.metadata = client.V1ObjectMeta(
            namespace=namespace, name=name, labels=labels
        )
        body.status = client.V1JobStatus()

        template = client.V1PodTemplate()
        template.template = client.V1PodTemplateSpec()

        image_pull_policy = self._image_pull_policy
        container = client.V1Container(
            name=container_name,
            image=container_image,
            image_pull_policy=image_pull_policy,
        )
        containers = [container]

        node_affinity = {}
        match_expressions = []
        for a in self._node_group_affinity:
            node_selector = client.V1NodeSelectorRequirement(
                key=a["key"], operator=a["operator"], values=a["value"]
            )
            match_expressions.append(node_selector)
        node_selector_terms = client.V1NodeSelectorTerm(
            match_expressions=match_expressions
        )
        node_affinity = client.V1NodeAffinity(
            required_during_scheduling_ignored_during_execution=client.V1NodeSelector(
                node_selector_terms=[node_selector_terms]
            )
        )

        node_tolerations = []
        for t in self._tolerations:
            toleration = client.V1Toleration(
                effect=t["effect"], key=t["key"], operator=t["operator"], value=t["value"]
            )
            node_tolerations.append(toleration)

        template.template.spec = client.V1PodSpec(
            affinity=node_affinity,
            containers=containers,
            tolerations=node_tolerations,
            restart_policy="Never",
        )
        template.template.metadata = client.V1ObjectMeta(labels=labels)

        body.spec = client.V1JobSpec(
            ttl_seconds_after_finished=0, template=template.template
        )
        return body

    def scale_workers(self, num_new_workers):
        labels = dict()
        labels["worker-type"] = self._worker_type
        labels["worker-group"] = self._worker_group

        for i in range(num_new_workers):
            name = self._worker_type + "-" + self.generate_random_id()
            image_name = self._image_name
            body = self.create_job_object(
                name,
                container_image=image_name,
                namespace=self._k8s_namespace,
                container_name=self._worker_type,
                labels=labels,
            )
            try:
                self._api_inst.create_namespaced_job(
                    self._k8s_namespace, body, pretty=True
                )
            except ApiException as e:
                print("Error creating new worker job: ", e.body, flush=True)

    def pod_is_running(self, pod):
        pod_is_running = False
        for condition in pod.status.conditions or []:
            if condition.type == "ContainersReady" and condition.status == "True":
                pod_is_running = True
                break
        return pod_is_running

    def pod_is_terminated(self, pod):
        pod_is_terminated = False
        for container_status in pod.status.container_statuses or []:
            state = container_status.state
            if state.terminated:
                pod_is_terminated = True
                break
        return pod_is_terminated

    def get_workers_count(self):
        label_selector = f"worker-type={self._worker_type},worker-group={self._worker_group}"
        cnt_running = 0
        cnt_pending = 0
        try:
            jobs = self._api_inst.list_namespaced_job(
                namespace=self._k8s_namespace, label_selector=label_selector
            )
            if jobs:
                for j in jobs.items:
                    pod_selector = "job-name=" + j.metadata.name
                    pods = self._core_v1.list_namespaced_pod(
                        namespace=self._k8s_namespace, label_selector=pod_selector
                    )
                    for pod in pods.items:
                        pod_is_terminated = self.pod_is_terminated(pod)
                        if not pod_is_terminated:
                            pod_is_running = self.pod_is_running(pod)
                            if pod_is_running:
                                cnt_running += 1
                            else:
                                cnt_pending += 1
        except Exception as e:
            error = e
            if isinstance(e, ApiException):
                error = e.body
            print({
                    "message": "Error getting workers count",
                    "label_selector": label_selector,
                    "error": error,
                }, flush=True,
            )
        return {"cnt_running": cnt_running, "cnt_pending": cnt_pending}

    def get_message_count(self):
        message_count = self._queue_watcher.get_message_count()
        return message_count

    def __init__(self):
        self._environment = environ["environment"].lower()
        self._worker_type = environ["worker_type"]
        self._worker_group = environ["worker_group"]
        self._image_name = environ["image_name"]
        self._image_pull_policy = environ["image_pull_policy"]

        self._node_group_affinity = [
            {
                "key": "worker_group", 
                "operator": "Equal", 
                "value": self._worker_group
            }
        ]

        self._tolerations = [
            {
                "effect": "NoSchedule", 
                "key": "worker_group", 
                "operator": "Equal", 
                "value": self._worker_group
            }
        ]

        self._target_queue_size = int(environ["target_queue_size"])
        self._force_empty_queue_interval = environ["force_empty_queue_interval"]
        self._scale_increment = int(environ["scale_increment"])
        self._check_trigger_interval = int(environ["check_trigger_interval"])
        self._k8s_namespace = environ["k8s_namespace"]

        if self._environment == "kubernetes":
            # Get kubernetes api credentials from a pod in a kubernetes cluster
            k8s_config.load_incluster_config()
            k8s_configuration = client.Configuration()
            token_file = open("/var/run/secrets/kubernetes.io/serviceaccount/token")
            token = token_file.read()
            token_file.close()
            k8s_configuration.api_key["authorization"] = token
            k8s_configuration.api_key_prefix["authorization"] = "Bearer"
            k8s_configuration.host = "https://kubernetes.default.svc"
            k8s_configuration.verify_ssl = False
            client.Configuration.set_default(k8s_configuration)
        else:
            # Get kubernetes api credentials from kubectl (outside of a kubernetes cluster)
            k8s_config.load_kube_config()
            k8s_configuration = client.Configuration()
            k8s_configuration.verify_ssl = False

        self._apps_v1 = client.AppsV1Api()
        self._api_inst = client.BatchV1Api(client.ApiClient(k8s_configuration))
        self._core_v1 = client.CoreV1Api()

        rmq_user_name = environ["rmq_user_name"]
        rmq_password = environ["rmq_password"]
        rmq_host = environ["rmq_host"]
        rmq_port = environ["rmq_port"]
        rmq_vhost = environ["rmq_vhost"]
        rmq_uri = f"amqp://{rmq_user_name}:{rmq_password}@{rmq_host}:{rmq_port}/{rmq_vhost}"
        queue_name = environ["queue_name"]
        self._queue_watcher = QueueWatcher(rmq_uri, queue_name, True, False, False)

        self._last_active_time = datetime.now() - timedelta(milliseconds=300000)

    def run(self):
        while True:
            message_count = self.get_message_count()
            worker_counts = self.get_workers_count()

            num_workers_total = worker_counts["cnt_running"] + worker_counts["cnt_pending"]

            if worker_counts["cnt_running"] > 0:
                self._last_active_time = datetime.now()

            num_workers_target = num_workers_total
            if (
                worker_counts["cnt_pending"] < 1
                and message_count > self._target_queue_size
            ):
                num_workers_target = self._scale_increment
                if num_workers_total > 0:
                    num_workers_target = num_workers_total + self._scale_increment

            # Don't leave small numbers of messages sitting in the queue for too long
            elif message_count > 0 and num_workers_total < 1:
                curr_time = datetime.now()
                td = curr_time - self._last_active_time
                if int(td.total_seconds() * 1000) > self._force_empty_queue_interval:
                    num_workers_target = num_workers_total + self._scale_increment

            if num_workers_target > num_workers_total:
                delta = num_workers_target - num_workers_total
                if delta > 0:
                    print({
                            "message": "Scaling up workers",
                            "message_count": message_count,
                            "worker_type": self._worker_type,
                            "num_workers_total": num_workers_total,
                            "num_workers_target": num_workers_target,
                        }, flush=True,
                    )
                    self.scale_workers(delta)
            time.sleep(self._check_trigger_interval)


def main():
    auto_scaler = AutoScaler()
    auto_scaler.run()


if __name__ == "__main__":
    main()
