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

import paho.mqtt.publish as publish
import socket
import binascii
import time
import sys
import string
import ConfigParser
import io
import getopt

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

configfile = "config.ini"

def main(argv):
    # Get command-line arguments
    try:
      opts, args = getopt.getopt(argv,"hc:",["config="])
    except getopt.GetoptError:
        print 'ginlong-wifi-mqtt.py -c <configfile>'
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print 'ginlong-wifi-mqtt.py -c <configfile>'
            sys.exit()

        elif opt in ("-c", "--config"):
            configfile = arg

    # Read config file
    with open(configfile) as f:
            sample_config = f.read()
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.readfp(io.BytesIO(sample_config))

    # Variables
    listen_address = config.get('DEFAULT', 'listen_address')
    listen_port = int(config.get('DEFAULT', 'listen_port'))
    client_id = config.get('MQTT', 'client_id')
    mqtt_server = config.get('MQTT', 'mqtt_server')
    mqtt_port = int(config.get('MQTT', 'mqtt_port'))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # create socket on required port
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((listen_address, listen_port))
    sock.listen(1) # listen on port

    while True:

        print 'Waiting for a connection...'
        
        conn, addr = sock.accept()				# wait for inverter connection
    
        print 'Connection from', addr
        
        rawdata = conn.recv(1000)				# read incoming data
        hexdata = binascii.hexlify(rawdata)		# convert data to hex

        if(hexdata[0:8] == header and len(hexdata) == data_size):		# check for valid data
            msgs = []
            mqtt_topic = ''.join(["ginlong", "/", client_id, "/"])   # Create the topic base using the client_id

            watt_now = str(int(hexdata[inverter_now*2:inverter_now*2+4],16))    		# generating power in watts
            msgs.append((mqtt_topic + "watt_now", watt_now, 0, False))

            kwh_day = str(float(int(hexdata[inverter_day*2:inverter_day*2+4],16))/100)	# running total kwh for day
            msgs.append((mqtt_topic + "kwh_day", kwh_day, 0, False))

            kwh_total = str(int(hexdata[inverter_tot*2:inverter_tot*2+8],16)/10)		# running total kwh from installation
            msgs.append((mqtt_topic + "kwh_total", kwh_total, 0, False))

            temp = str(float(int(hexdata[inverter_temp*2:inverter_temp*2+4],16))/10)    # temperature
            msgs.append((mqtt_topic + "temp", temp, 0, False))

            dc_volts1= str(float(int(hexdata[inverter_vdc1*2:inverter_vdc1*2+4],16))/10)	# input dc volts from chain 1
            msgs.append((mqtt_topic + "dc_volts1", dc_volts1, 0, False))

            dc_volts2= str(float(int(hexdata[inverter_vdc2*2:inverter_vdc2*2+4],16))/10)	# input dc volts from chain 2
            msgs.append((mqtt_topic + "dc_volts2", dc_volts2, 0, False))

            dc_amps1 = str(float(int(hexdata[inverter_adc1*2:inverter_adc1*2+4],16))/10)	# input dc amps from chain 1
            msgs.append((mqtt_topic + "dc_amps1", dc_amps1, 0, False))

            dc_amps2 = str(float(int(hexdata[inverter_adc2*2:inverter_adc2*2+4],16))/10)	# input dc amps from chain 2
            msgs.append((mqtt_topic + "dc_amps2", dc_amps2, 0, False))

            ac_volts = str(float(int(hexdata[inverter_vac*2:inverter_vac*2+4],16))/10)		# output ac volts
            msgs.append((mqtt_topic + "ac_volts", ac_volts, 0, False))

            ac_amps = str(float(int(hexdata[inverter_aac*2:inverter_aac*2+4],16))/10)		# output ac amps
            msgs.append((mqtt_topic + "ac_amps", ac_amps, 0, False))

            ac_freq = str(float(int(hexdata[inverter_freq*2:inverter_freq*2+4],16))/100)	# output ac frequency hertz
            msgs.append((mqtt_topic + "ac_freq", ac_freq, 0, False))

            kwh_yesterday = str(float(int(hexdata[inverter_yes*2:inverter_yes*2+4],16))/100)	# yesterday's kwh
            msgs.append((mqtt_topic + "kwh_yesterday", kwh_yesterday, 0, False))

            kwh_month = str(int(hexdata[inverter_mth*2:inverter_mth*2+4],16))					# running total kwh for month
            msgs.append((mqtt_topic + "kwh_month", kwh_month, 0, False))

            kwh_lastmonth = str(int(hexdata[inverter_lmth*2:inverter_lmth*2+4],16))				# running total kwh for last month
            msgs.append((mqtt_topic + "kwn_lastmonth", kwh_lastmonth, 0, False))

            timestamp = (time.strftime("%F %H:%M"))		# get date time

            publish.multiple(msgs, hostname=mqtt_server, port=mqtt_port, auth=None)

    conn.close()

if __name__ == "__main__":
   main(sys.argv[1:])
