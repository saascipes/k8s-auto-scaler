import ctypes
import json
import sys
import time
import threading
import traceback

from datetime import datetime
from os import environ, _exit
from pika.exchange_type import ExchangeType
from socket import gethostname
from threading import Thread, Event

from rmq_consumer import AsyncConsumer


NULL = 0


def raise_exception_in_thread(thread_obj, exception):
    found = False
    target_tid = 0
    for tid, tobj in threading._active.items():
        if tobj is thread_obj:
            found = True
            target_tid = tid
            break

    if not found:
        raise ValueError("Invalid thread object")

    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(target_tid), ctypes.py_object(exception)
    )
    if ret == 0:
        raise ValueError("Invalid thread ID")
    elif ret > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, NULL)
        raise SystemError("PyThreadState_SetAsyncExc failed")


class Worker(object):
    """Auto reconnect rabbitmq consumer for a queue worker - messages are processed in parallel up to a max number of threads"""

    def on_message(self, delivery_tag, body, rmq_connector):
        self._last_active_time = datetime.now()
        message = json.loads(body)
        context = message | {"host": gethostname()}
        time.sleep(1)
        print(
            f"Processed message: {context}",
            flush=True,
        )
        rmq_connector.acknowledge_message(delivery_tag)

    def create_async_consumer(self):
        self._consumer = AsyncConsumer(
            self._amqp_uri,
            {
                "exch": self._exch_name,
                "exch_type": ExchangeType.topic,
                "durable": True,
                "queue_name": self._queue_name,
                "exclusive": False,
                "auto_delete": False,
                "routing_key": None,
                "prefetch_count": 1,
                "auto_ack": False,
                "on_message": self.on_message,
            },
        )

    def start_async_consumer(self):
        """
        Start the rabbitmq consumer - stop it when stop_event is set
        """
        self._consumer.run()

    def check_processor_status(self, args1, stop_event):
        """
        Shut down this instance if idle for more than the threshold
        :return:
        :rtype:
        """
        while not stop_event.is_set():
            try:
                if self._cnt_active_messages > 0:
                    continue
                curr_time = datetime.now()
                td = curr_time - self._last_active_time
                if td.total_seconds() > self._max_idle_seconds:
                    self._terminating = True
                    print("Stopping worker due to max idle time exceeded", flush=True)
                    break
            except Exception as e:
                print(e, flush=True)
            stop_event.wait(1)

    def gracefully_shutdown(self):
        try:
            raise_exception_in_thread(self._async_consumer_thread, SystemExit)
            self._async_consumer_thread.join()
            self._check_processor_status_thread_stop.set()
            self._check_processor_status_thread.join()
            sys.exit(0)
        except Exception as ex:
            print(ex, flush=True)
            traceback.print_exc(file=sys.stdout)
            _exit(0)

    def __init__(self, **params):
        self._reconnect_delay = 0
        self._cnt_active_messages = 0
        self._exch_name = params["exch_name"]
        self._queue_name = params["queue_name"]
        self._amqp_uri = params["amqp_uri"]
        self._max_idle_seconds = params["max_idle_seconds"]

        self._terminating = False
        self._stopped = False

        self.create_async_consumer()
        self._async_consumer_thread = Thread(
            target=self.start_async_consumer,
        )

        self._check_processor_status_thread_stop = None
        self._check_processor_status_thread = None
        self._last_active_time = datetime.now()

    def run(self):
        print("Starting Worker", flush=True)
        self._async_consumer_thread.start()

        if self._max_idle_seconds > 0:
            self._check_processor_status_thread_stop = Event()
            self._check_processor_status_thread = Thread(
                target=self.check_processor_status,
                args=(1, self._check_processor_status_thread_stop),
            )
            self._check_processor_status_thread.start()

            while True:
                try:
                    if self._terminating:
                        if self._cnt_active_messages < 1:
                            self.gracefully_shutdown()
                        else:
                            print(
                                f"Unable to terminate - {self._cnt_active_messages} active messages",
                                flush=True,
                            )
                    time.sleep(2)
                except KeyboardInterrupt:
                    print("process interrupted - exiting", flush=True)
                    self.gracefully_shutdown()
                self._maybe_reconnect()

    def _maybe_reconnect(self):
        if self._consumer.should_reconnect:
            print("Stopping rmq connection", flush=True)
            try:
                raise_exception_in_thread(self._async_consumer_thread, SystemExit)
                self._async_consumer_thread.join()
            except Exception:
                pass
            self._stopped = True
            reconnect_delay = self._get_reconnect_delay()
            print("Reconnecting after %d seconds", reconnect_delay, flush=True)
            time.sleep(reconnect_delay)
            self.create_async_consumer()
            self._async_consumer_thread = Thread(
                target=self.start_async_consumer,
            )
            self._async_consumer_thread.start()

    def _get_reconnect_delay(self):
        if self._consumer.was_consuming:
            self._reconnect_delay = 0
        else:
            self._reconnect_delay += 1
        if self._reconnect_delay > 30:
            self._reconnect_delay = 30
        return self._reconnect_delay


def main():
    host = "rabbitmq"
    port = "5672"
    username = "autoScaler"
    password = "auto1234"
    vhost = "jobsToDo"
    params = {
        "exch_name": "test-exch",
        "queue_name": "test-queue",
        "amqp_uri": f"amqp://{username}:{password}@{host}:{port}/{vhost}",
        "max_idle_seconds": 20,
    }

    worker = Worker(**params)
    worker.run()


if __name__ == "__main__":
    main()
