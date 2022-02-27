#!/usr/bin/python

###################################################################################################
#
#  Copyright 2015 Graham Whiteside
#  Copyright 2021 Scott Ware
#
#  This program is free software: you can redistribute it and/or modify it under the terms of the
#  GNU General Public License as published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
#  even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
#  General Public License for more details.
#
#  You can browse the GNU license here: <http://www.gnu.org/licenses/>.
#
###################################################################################################

import paho.mqtt.client as mqtt
import argparse
import socket
import binascii
import time
import sys
import string
import io
import json

# Inverter values found (so far) all big endian 16 bit unsigned
header = '685951b0' 				# hex stream header
data_size = 206                     # hex stream size 
inverter_temp = 31 					# offset 31 & 32 temperature (/10)
inverter_vdc1 = 33 					# offset 33 & 34 DC volts chain 1 (/10)
inverter_vdc2 = 35 					# offset 35 & 36 DC volts chain 2 (/10)
inverter_adc1 = 39 					# offset 39 & 40 DC amps chain 1 (/10)
inverter_adc2 = 41 					# offset 41 & 42 DC amps chain 2 (/10)
inverter_aac = 45					# offset 45 & 46 AC output amps (/10)
inverter_vac = 51 					# offset 51 & 52 AC output volts (/10)
inverter_freq = 57 					# offset 57 & 58 AC frequency (/100)
inverter_now = 59 					# offset 59 & 60 currant generation Watts
inverter_yes = 67 					# offset 67 & 68 yesterday kwh (/100)
inverter_day = 69 					# offset 69 & 70 daily kWh (/100)
inverter_tot = 71 					# offset 71 & 72 & 73 & 74 total kWh (/10)
inverter_mth = 87					# offset 87 & 88 total kWh for month 
inverter_lmth = 91					# offset 91 & 92 total kWh for last month 

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Glow MQTT Client.')
parser.add_argument('--listen_address', required=False, default='0.0.0.0', help='IP address to listen on. Default: 0.0.0.0')
parser.add_argument('--listen_port', required=False, default=9999, help='Port to listen on. Default: 9999')
parser.add_argument('--client_id', required=False, help='Client ID to differentiate between inverters. Default: home')
parser.add_argument('--mqtt_address', required=False, default='localhost',  help='MQTT broker address. Default: localhost')
parser.add_argument('--mqtt_port', required=False, default=1883, help='MQTT port. Default: 1883')
parser.add_argument('--mqtt_username', required=False, default='', help='MQTT username.')
parser.add_argument('--mqtt_password', required=False, default='', help='MQTT password.')
parser.add_argument('--hass', default=False, action='store_true', help='Enable Home Assistant auto-discovery')
args = vars(parser.parse_args())

# Variables
listen_address = args['listen_address']
listen_port = args['listen_port']
client_id = args['client_id']
mqtt_address = args['mqtt_address']
mqtt_port = args['mqtt_port']
mqtt_username = args['mqtt_username']
mqtt_password = args['mqtt_password']
homeassistant = args.get('homeassistant')
mqtt_topic = ''.join(["ginlong", "/", "inverter", "_", client_id])

def on_connect(client, obj, flags, rc):
    print("MQTT connected...")

# Create MQTT client
mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.username_pw_set(mqtt_username,mqtt_password)
mqttc.connect(mqtt_address, mqtt_port, 60)
mqttc.loop_start()

# Home Assistant
if (homeassistant):
    print("Configuring Home Assistant...")

    discovery_msgs = []

    # Generating power in watts
    watt_now_topic = "homeassistant/sensor/ginlong_inverter_" + client_id + "/watt_now/config"
    watt_now_payload = {"device_class": "power", "state_class": "measurement", "device": {"identifiers": ["ginlong_inverter_" + client_id], "manufacturer": "Ginlong", "name": client_id}, "unique_id": "ginlong_inverter_" + client_id + "_watt_now", "name": "ginlong_inverter_" + client_id + "_current_power", "state_topic": mqtt_topic, "unit_of_measurement": "W", "value_template": "{{ value_json.watt_now}}" }
    mqttc.publish(watt_now_topic, json.dumps(watt_now_payload), retain=True)

    # Running total kWH for the day
    kwh_day_topic = "homeassistant/sensor/ginlong_inverter_" + client_id + "/kwh_day/config"
    kwh_day_payload = {"device_class": "energy", "state_class": "total_increasing", "device": {"identifiers": ["ginlong_inverter_" + client_id], "manufacturer": "Ginlong", "name": client_id}, "unique_id": "ginlong_inverter_" + client_id + "_kwh_day", "name": "ginlong_inverter_" + client_id + "_yield_today", "state_topic": mqtt_topic, "unit_of_measurement": "kWh", "value_template": "{{ value_json.kwh_day}}"}
    mqttc.publish(kwh_day_topic, json.dumps(kwh_day_payload), retain=True)

    # Running total kWH for all time
    kwh_total_topic = "homeassistant/sensor/ginlong_inverter_" + client_id + "/kwh_total/config"
    kwh_total_payload = {"device_class": "energy", "state_class": "total_increasing", "device": {"identifiers": ["ginlong_inverter_" + client_id], "manufacturer": "Ginlong", "name": client_id}, "unique_id": "ginlong_inverter_" + client_id + "_kwh_total", "name": "ginlong_inverter_" + client_id + "_total_yield", "state_topic": mqtt_topic, "unit_of_measurement": "kWh", "value_template": "{{ value_json.kwh_total}}"}
    mqttc.publish(kwh_total_topic, json.dumps(kwh_total_payload), retain=True)

    # Temperature
    temp_topic = "homeassistant/sensor/ginlong_inverter_" + client_id + "/temp/config"
    temp_payload = {"device_class": "temperature", "state_class": "measurement", "device": {"identifiers": ["ginlong_inverter_" + client_id], "manufacturer": "Ginlong", "name": client_id}, "unique_id": "ginlong_inverter_" + client_id + "_temp", "name": "ginlong_inverter_" + client_id + "_temperature", "state_topic": mqtt_topic, "unit_of_measurement": "°C", "value_template": "{{ value_json.temp}}"}
    mqttc.publish(temp_topic, json.dumps(temp_payload), retain=True)

# Create socket on required port
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((listen_address, listen_port))
sock.listen(1)

while True:

    print('Waiting for a connection...')
    
    sock.settimeout(None)
    conn, addr = sock.accept()
    conn.settimeout(60.0)

    try:
        print('Connection from', addr)

        # Read incoming data
        rawdata = conn.recv(1000)
        hexdata = rawdata.hex()

        if (hexdata[0:8] == header and len(hexdata) == data_size):
            status = {}

            # Current power in watts
            watt_now = int(hexdata[inverter_now*2:inverter_now*2+4],16)
            status["watt_now"] = watt_now

            # Yield today
            kwh_day = float(int(hexdata[inverter_day*2:inverter_day*2+4],16))/100
            status["kwh_day"] = kwh_day

            # Total Yield
            kwh_total = int(hexdata[inverter_tot*2:inverter_tot*2+8],16)/10
            status["kwh_total"] = kwh_total

            # Temperature
            temp = float(int(hexdata[inverter_temp*2:inverter_temp*2+4],16))/10
            status["temp"] = temp

            # Input DC Volts from Chain 1
            dc_volts1= float(int(hexdata[inverter_vdc1*2:inverter_vdc1*2+4],16))/10
            status["dc_volts1"] = dc_volts1

            # Input DC Volts from Chain 2
            dc_volts2= float(int(hexdata[inverter_vdc2*2:inverter_vdc2*2+4],16))/10
            status["dc_volts2"] = dc_volts2

            # Input DC Amps from Chain 1
            dc_amps1 = float(int(hexdata[inverter_adc1*2:inverter_adc1*2+4],16))/10
            status["dc_amps1"] = dc_amps1

            # Input DC Amps from Chain 2
            dc_amps2 = float(int(hexdata[inverter_adc2*2:inverter_adc2*2+4],16))/10
            status["dc_amps2"] = dc_amps2

            # Output AC Volts
            ac_volts = float(int(hexdata[inverter_vac*2:inverter_vac*2+4],16))/10
            status["ac_volts"] = ac_volts

            # Output AC Amps
            ac_amps = float(int(hexdata[inverter_aac*2:inverter_aac*2+4],16))/10
            status["ac_amps"] = ac_amps

            # Output AC Frequency Hz
            ac_freq = float(int(hexdata[inverter_freq*2:inverter_freq*2+4],16))/100
            status["ac_freq"] = ac_freq

            # Yield Yesterday
            kwh_yesterday = float(int(hexdata[inverter_yes*2:inverter_yes*2+4],16))/100
            status["kwh_yesterday"] = kwh_yesterday

            # Yield Month
            kwh_month = int(hexdata[inverter_mth*2:inverter_mth*2+4],16)
            status["kwh_month"] = kwh_month

            # Yield Previous Month
            kwh_lastmonth = int(hexdata[inverter_lmth*2:inverter_lmth*2+4],16)
            status["kwh_lastmonth"] = kwh_lastmonth

            print(status)

            mqttc.publish(mqtt_topic, json.dumps(status), retain=True)

        else:
            print("Unsupported payload: ", hexdata)

    except socket.timeout:
        print("Socket timeout occurred!")

    except:
        print("Exception: ", sys.exc_info()[0])

    finally:
        conn.shutdown(socket.SHUT_RDWR)

