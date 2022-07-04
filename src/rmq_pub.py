import json
import pika

from os import environ


user_name = environ.get("rmq_user_name")
password = environ.get("rmq_password")
host = environ.get("rmq_host")
port = int(environ.get("rmq_port"))
vhost = environ.get("rmq_vhost")
exch = environ.get("exch_name")
queue_name = environ.get("queue_name")
num_messages_to_publish = int(environ.get("num_messages_to_publish"))

credentials = pika.PlainCredentials(user_name, password)
params = pika.ConnectionParameters(host, port, vhost, credentials)
rmq_con = pika.BlockingConnection(params)


channel = rmq_con.channel()
channel.exchange_declare(exchange=exch, exchange_type="topic", durable=True)
channel.queue_declare(queue=queue_name, durable=True)
channel.queue_bind(exchange=exch, queue=queue_name, routing_key=queue_name)

for _ in range(num_messages_to_publish):
    outmsg_json = json.dumps({"message": "contents"})
    channel.basic_publish(exchange=exch, routing_key=queue_name, body=outmsg_json, properties=pika.BasicProperties(delivery_mode=2))
