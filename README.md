
# Ginlong WiFi MQTT Bridge
Collect data from a second generation Ginlong/Solis inverter equipped with a WIFI stick and publish to an MQTT broker.

# Introduction
A Ginlong/Solis second generation inverter equipped with a WIFI 'stick' sends it's data to the Ginlong
Monitoring website (http://www.ginlongmonitoring.com/) once every six minutes, when the inverter is 
live. It is also possible to log onto the WIFI 'stick' locally with a browser to configure the inverter
and read the six minute updated generation stats. The WiFi stick also has the ability to send statistics 
to 2 further remote servers over TCP or UDP.

# Configuring the Inverter
Log onto your inverter and click on 'Advanced'
Now click 'Remote server'
Enter a new ip address for 'Server B' (your computer) enter a port number (default 9999) select 'TCP' 
Click the 'Test' button and a tick should appear.
Click 'Save' and and when prompted 'Restart'

# Running the Application
Copy the 'config.ini.template' file to a new file called 'config.ini' and update the parameters accordingly.
'client_id' can be whatever you want it to be in order to identify the inverter you intend to connect.

Install dependencies:

    pip install -r requirements.txt

Run the application:

    python ./ginlong-wifi-mqtt.py

