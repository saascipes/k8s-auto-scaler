import pika
from pika.exceptions import AMQPConnectionError
from pika.exchange_type import ExchangeType
import time


class QueueWatcher(object):
    """
    Gets the number of messages in a queue
    """

    def __init__(self, amqp_url, queue_name, durable, exclusive, auto_delete):
        self._amqp_url = amqp_url
        self._queue_name = queue_name
        self._durable = durable
        self._exclusive = exclusive
        self._auto_delete = auto_delete
        self.init()

    def init(self):
        while True:
            try:
                parameters = pika.URLParameters(self._amqp_url)
                self._connection = pika.BlockingConnection(parameters)
                self._channel = self._connection.channel()
                self.assert_queue(False)
                break
            except AMQPConnectionError:
                print("Error connecting to RabbitMQ", flush=True)
                quit()
            except Exception as e:
                print(f"Error initializing QueueWatcher: {e}", flush=True)
                time.sleep(5)

    def close_connection(self):
        print("Closing connection", flush=True)
        self._connection.close()

    def close_channel(self):
        print("Closing the channel", flush=True)
        self._channel.close()

    def assert_queue(self, passive):
        """
        Make sure the queue exists to avoid an exception when getting the message count
        """
        return self._channel.queue_declare(
            queue=self._queue_name,
            passive=False,
            durable=self._durable,
            exclusive=self._exclusive,
            auto_delete=self._auto_delete,
        )

    def get_message_count(self):
        res = self.assert_queue(True)
        return res.method.message_count
