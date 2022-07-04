# k8s-auto-scaler
For a full explanation see [link to medium article].  
<br />

## Prerequisites
- Docker
- Kubernetes
- Helm

\* Note - may not run on Mac M1 if the bitnami RabbitMQ chart is still not compatible with the arm64 processor

## Install
1. Clone the repo
2. Build docker images
    ```
    $ ./bin/build_docker_images.sh
    ```
3. Install helm charts
    ```
    $ ./bin/install.sh
    ```
4. Publish test messages
    ```
    $ ./bin/publish_messages.sh
    ```
5. View worker scaler logs
    ```
    $ ./bin/view_worker_scaler_logs.sh
    ```
6. View worker logs (will display logs for the first worker created after publishing messages)
    ```
    $ ./bin/view_worker_logs.sh
    ```

## Notes
- The install script will install RabbitMQ and the Worker Scaler in the default namespace
- To access the RabbitMQ monitor, follow these steps after running the install script in bin/install.sh:
    1. Open a terminal window or DOS prompt on Windows
    2. Run
        ```
        $ kubectl port-forward service/rabbitmq 15672:15672
        ```
    3. Open a web browser and browse to localhost:15672
    4. Log in with username "autoScaler" and password "auto1234"
- To get a list of all running pods:
    ```
    $ kubectl get pod
    ```
- To get a list of the running worker pods:
    ```
    $ kubectl get pod | grep worker | grep -v scaler
    ```
- To view logs for a pod:
    ```
    kubectl logs -f pod/[pod name]
    ```
- To change the number of messages published modify the "num_messages_to_publish" environment variables in deploy/kubernetes/publish_messages_job.yaml
- To change worker scaler parameters, modify deploy/kubernetes/helm/templates/worker_scaler.yaml
- To uninstall
    ```
    $ ./bin/uninstall.sh
    ```