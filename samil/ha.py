from collections import namedtuple
from samil.mqttoutput import MqttOutput
import logging

class HomeAssistantDiscovery:

    __HA_SENSORS = [
        {
            'name': 'Operation Mode',
            'ha_sensor_type': 'sensor',
            'value_template': '{{ value_json.operation_mode }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'Total Operation Time',
            'ha_sensor_type': 'sensor',
            'unit_of_measurement': 'h',
            'value_template': '{{ value_json.total_operation_time }}',
            'icon': 'mdi:timer-outline'
        },
        {
            'name': 'PV1 Input Power',
            'ha_sensor_type': 'sensor',
            'device_class': 'power',
            'unit_of_measurement': 'W',
            'value_template': '{{ value_json.pv1_input_power }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'PV1 Voltage',
            'ha_sensor_type': 'sensor',
            'device_class': 'voltage',
            'unit_of_measurement': 'V',
            'value_template': '{{ value_json.pv1_voltage }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'PV1 Current',
            'ha_sensor_type': 'sensor',
            'device_class': 'current',
            'unit_of_measurement': 'A',
            'value_template': '{{ value_json.pv1_current }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'PV2 Input Power',
            'ha_sensor_type': 'sensor',
            'device_class': 'power',
            'unit_of_measurement': 'W',
            'value_template': '{{ value_json.pv2_input_power }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'PV2 Voltage',
            'ha_sensor_type': 'sensor',
            'device_class': 'voltage',
            'unit_of_measurement': 'V',
            'value_template': '{{ value_json.pv2_voltage }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'PV2 Current',
            'ha_sensor_type': 'sensor',
            'device_class': 'current',
            'unit_of_measurement': 'A',
            'value_template': '{{ value_json.pv2_current }}',
            'icon': 'mdi:solar-panel'
        },
        {
            'name': 'Output Power',
            'ha_sensor_type': 'sensor',
            'device_class': 'power',
            'unit_of_measurement': 'W',
            'value_template': '{{ value_json.output_power }}',
            'icon': 'mdi:lightning-bolt'
        },
        {
            'name': 'Energy Today',
            'ha_sensor_type': 'sensor',
            'device_class': 'energy',
            'unit_of_measurement': 'kWh',
            'value_template': '{{ value_json.energy_today }}',
            'icon': 'mdi:lightning-bolt'
        },
        {
            'name': 'Energy Total',
            'ha_sensor_type': 'sensor',
            'device_class': 'energy',
            'unit_of_measurement': 'kWh',
            'value_template': '{{ value_json.energy_total }}',
            'icon': 'mdi:lightning-bolt'
        },
        {
            'name': 'Grid Voltage',
            'ha_sensor_type': 'sensor',
            'device_class': 'voltage',
            'unit_of_measurement': 'V',
            'value_template': '{{ value_json.grid_voltage }}',
            'icon': 'mdi:transmission-tower'
        },
        {
            'name': 'Grid Current',
            'ha_sensor_type': 'sensor',
            'device_class': 'current',
            'unit_of_measurement': 'A',
            'value_template': '{{ value_json.grid_current }}',
            'icon': 'mdi:transmission-tower'
        },
        {
            'name': 'Grid Frequency',
            'ha_sensor_type': 'sensor',
            'unit_of_measurement': 'Hz',
            'value_template': '{{ value_json.grid_frequency }}',
            'icon': 'mdi:sine-wave'
        },
        {
            'name': 'Inverter Temperature',
            'ha_sensor_type': 'sensor',
            'device_class': 'temperature',
            'unit_of_measurement': '°C',
            'value_template': '{{ value_json.internal_temperature }}',
            'icon': 'mdi:thermometer'
        },
    ]

    def __init__(self, mqttOutput: MqttOutput, interval: float, haDiscoveryPrefix: str='homeassistant'):
        self.__logger = logging.getLogger(__name__)

        self.__mqttOutput = mqttOutput

        # Double the interval to allow time for late messages, add 1 to ensure it is always rounded up
        self.__expireAfter = int(interval * 2) + 1

        if haDiscoveryPrefix:
            self.__haDiscoveryPrefix = haDiscoveryPrefix
            if not haDiscoveryPrefix.endswith('/'):
                self.__haDiscoveryPrefix += '/'

    def publicize(self, inverters):
        for inverter in inverters:
            self.publicizeInverter(inverter)

    def publicizeInverter(self, inverter: namedtuple):
        modelDetails = inverter.inverter.model()
        inverterId = modelDetails['serial_number']

        for sensor in self.__HA_SENSORS:
            self._publicizeInverterSensor(inverterId, inverter.topic, modelDetails, sensor)

        self.__logger.info("Published {} sensors for inverter {}".format(len(self.__HA_SENSORS), inverterId))

    def _publicizeInverterSensor(self, inverterId: str, inverterTopic: str, modelDetails: dict, sensor):
        sensorName = self._getIdentifier(sensor['name'])

        topic = '{}{}/{}/{}/config'.format(
            self.__haDiscoveryPrefix,
            sensor.get('ha_sensor_type', 'sensor'),
            inverterId,
            sensorName
        )
        discoveryMessage=self._removeKeysWithNoValue({
            'name': '{} {}'.format(inverterId, sensor['name']),
            'device_class': sensor.get('device_class', ''),
            'state_topic': inverterTopic,
            'json_attributes_topic': inverterTopic,
            'unit_of_measurement': sensor.get('unit_of_measurement', ''),
            'value_template': sensor['value_template'],
            'icon': sensor.get('icon', ''),
            'unique_id': '{}_{}'.format(inverterId, sensorName),
            'device': {
                'identifiers': [
                    inverterId
                ],
                'manufacturer': modelDetails['manufacturer'],
                'model': modelDetails['model_name'],
                'name': inverterId,
                'sw_version': modelDetails['firmware_version']
            },
            'expire_after': self.__expireAfter,
            'force_update': True
        })
        self.__mqttOutput.publish(topic, discoveryMessage)
        self.__logger.debug("Published message for inverter {} sensor '{}'".format(inverterId, sensor['name']))

    @staticmethod
    def _getIdentifier(name: str):
        return name.replace(' ', '_').lower()

    @staticmethod
    def _removeKeysWithNoValue(dict: dict):
        return {i:j for i,j in dict.items() if j}