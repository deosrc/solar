""" MQTT status upload """
from decimal import Decimal
import json
from paho.mqtt.client import Client as MQTTClient

class MqttOutput:

    def __init__(self, host: str, client_id: str, tls: bool, username: str, password: str, port: int=1883, interface: str=None):
        self.__client = MQTTClient(client_id=client_id)
        if tls:
            self.__client.tls_set()
        if username:
            self.__client.username_pw_set(username, password)

        self.__host = host
        self.__port = port
        self.__interface = interface

    def connect(self):
        print("Connecting to MQTT broker at {}:{}".format(self.__host, self.__port))
        self.__client.connect(host=self.__host, port=self.__port, bind_address=self.__interface or '')
        self.__client.loop_start()  # Starts handling MQTT traffic in separate thread

    def publish(self, topic: str, message: dict):
        jsonMessage = json.dumps(message, cls=DecimalEncoder, separators=(',', ':'))  # Compact encoding
        self.__client.publish(topic=topic, payload=jsonMessage)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if self.__client and self.__client.is_connected:
            self.__client.disconnect()


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal to float.

    Note: precision is lost here!
    """

    def default(self, o):
        """See base class."""
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)