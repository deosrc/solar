from collections import namedtuple
from samil.mqttoutput import MqttOutput
import logging

class HomeAssistantDiscovery:

    def __init__(self, mqttOutput: MqttOutput, interval: float, haDiscoveryPrefix: str='homeassistant'):
        self.__logger = logging.getLogger(__name__)

        self.__mqttOutput = mqttOutput

        # Double the interval to allow time for late messages, add 1 to ensure it is always rounded up
        self.__expireAfter = int(interval * 2) + 1

        if haDiscoveryPrefix:
            self.__haDiscoveryPrefix = haDiscoveryPrefix
            if not haDiscoveryPrefix.endswith('/'):
                self.__haDiscoveryPrefix += '/'

    def publicizeInverter(self, inverter: namedtuple, statusKeys: list):
        modelDetails = inverter.inverter.model()

        for sensorId in statusKeys:
            self._publicizeInverterSensor(modelDetails, sensorId, inverter.topic)

        self.__logger.info("Published {} sensors for inverter {}".format(len(statusKeys), modelDetails['serial_number']))

    def _publicizeInverterSensor(self, inverterModel: dict, sensorId: str, stateTopic: str):
        sensorName = self._generateSensorName(inverterModel['serial_number'], sensorId)

        topic = self._getTopic(inverterModel, sensorId)
        discoveryMessage = self._getBaseMessage(inverterModel, sensorId, sensorName, stateTopic)
        self._addSensorSpecificAttributes(discoveryMessage, sensorId)

        discoveryMessage = self._removeKeysWithNoValue(discoveryMessage)
        self.__mqttOutput.publish(topic, discoveryMessage)
        self.__logger.debug("Published message for inverter {} sensor '{}'".format(inverterModel['serial_number'], sensorId))

    @staticmethod
    def _generateSensorName(serialNumber, sensorId):
        attributeName = sensorId.replace('_', ' ').title().replace('pv', 'PV')
        return "{} {}".format(serialNumber, attributeName)

    def _getTopic(self, inverterModel, sensorId):
        return '{}sensor/{}/{}/config'.format(
            self.__haDiscoveryPrefix,
            inverterModel['serial_number'],
            sensorId
        )

    def _getBaseMessage(self, inverterModel, sensorId, sensorName, stateTopic):
        serialNumber = inverterModel['serial_number']
        return {
            'name': sensorName,
            'state_topic': stateTopic,
            'json_attributes_topic': stateTopic,
            'value_template': '{{{{ value_json.{} }}}}'.format(sensorId),
            'unique_id': '{}_{}'.format(serialNumber, sensorId),
            'device': {
                'identifiers': [
                    serialNumber
                ],
                'manufacturer': inverterModel['manufacturer'],
                'model': inverterModel['model_name'],
                'name': serialNumber,
                'sw_version': inverterModel['firmware_version']
            },
            'expire_after': self.__expireAfter,
            'force_update': True
        }

    @staticmethod
    def _addSensorSpecificAttributes(baseMessage, sensorId):
        if 'temperature' in sensorId:
            baseMessage['device_class'] = 'temperature'
            baseMessage['unit_of_measurement'] = '°C'
            baseMessage['icon'] = 'mdi:thermometer'
        elif 'time' in sensorId:
            baseMessage['unit_of_measurement'] = 'h'
            baseMessage['icon'] = 'mdi:timer-outline'
        elif 'power' in sensorId:
            baseMessage['device_class'] = 'power'
            baseMessage['unit_of_measurement'] = 'W'
            baseMessage['icon'] = 'mdi:lightning-bolt'
        elif 'current' in sensorId:
            baseMessage['device_class'] = 'current'
            baseMessage['unit_of_measurement'] = 'A'
            if sensorId.startswith('pv'):
                baseMessage['icon'] = 'mdi:current-dc'
            else:
                baseMessage['icon'] = 'mdi:current-ac'
        elif 'voltage' in sensorId:
            baseMessage['device_class'] = 'voltage'
            baseMessage['unit_of_measurement'] = 'V'
            baseMessage['icon'] = 'mdi:lightning-bolt'
        elif 'energy' in sensorId:
            baseMessage['device_class'] = 'energy'
            baseMessage['unit_of_measurement'] = 'kWh'
            baseMessage['icon'] = 'mdi:solar-power'
        elif 'frequency' in sensorId:
            baseMessage['unit_of_measurement'] = 'Hz'
            baseMessage['icon'] = 'mdi:sine-wave'
        else:
            baseMessage['icon'] = 'mdi:solar-panel'

    @staticmethod
    def _removeKeysWithNoValue(dict: dict):
        return {i:j for i,j in dict.items() if j}