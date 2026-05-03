Smart Obstacle Detection Cane for Visually Impaired People
A IoT Project by Adeel Ahmad and Ali Akrama
Department of Information Technology


Overview

This project is a working prototype of a smart assistive cane designed for people who are blind or visually impaired. It was built using affordable off-the-shelf hardware centered around a Raspberry Pi Zero 2W and costs approximately 85 USD in total, which is significantly cheaper than commercial assistive devices that typically cost over 2000 USD.

The cane uses a camera to identify objects in front of the user, a laser distance sensor to measure how far those objects are, and gives feedback through two channels at the same time. First, it speaks the object name and distance through Bluetooth headphones. Second, it vibrates a motor in different patterns depending on how close the obstacle is. The system runs fully automatically when powered on and does not require a phone, laptop, or any other device to operate.


Why We Built This

According to the World Health Organization, over 2.2 billion people worldwide live with some form of visual impairment. In many countries, especially in the Arab world and South Asia, affordable assistive navigation tools are simply not available. Traditional white canes only detect ground-level obstacles through touch and cannot identify what is in front of the user or how far away it is.

This project attempts to bridge that gap using modern computer vision and embedded AI on hardware that is accessible in most parts of the world. The goal was not to compete with high-end commercial products but to build something that actually works, costs very little, and could realistically be assembled and maintained by a student or a small clinic.


Medical and Healthcare Relevance

Visual impairment is classified as a disability under international health standards and has significant impact on independence, mental health, and quality of life. People who are blind face daily risks from obstacles that sighted people naturally avoid without thinking, such as open doors, furniture, steps, and other people.

This device addresses a real clinical need in rehabilitation medicine and assistive healthcare. It can be particularly useful in hospital corridors, rehabilitation centers, and home environments where a person with low vision or total blindness needs to navigate independently. The spoken distance information helps the user make real-time spatial decisions, while the vibration motor provides a backup warning channel that works even when the user cannot hear clearly.

The design also considers the reality that many visually impaired patients in low-income settings cannot afford occupational therapy tools or commercial navigation aids. A device under 100 USD that a family can build themselves has genuine potential for clinical adoption in resource-limited healthcare settings.


What Was Actually Built and What Works

Object detection using a camera and AI model. The camera captures video frames and a computer vision model called SSD MobileNet V1, trained on the COCO dataset, identifies what is in each frame. This is real computer vision running locally on the device with no internet connection required.

Distance measurement using a laser sensor. The VL53L0X Time-of-Flight sensor fires an invisible laser and measures how long it takes to bounce back. This gives an accurate distance reading in centimeters from roughly 5 cm to 200 cm.

Audio feedback through Bluetooth headphones. When an object is detected, the system speaks its name and distance. For example it will say person 80 centimeters or chair 120 centimeters. If no object is identified by the camera but the distance sensor detects something close, it says obstacle followed by the distance.

Vibration feedback through a motor. The motor vibrates in patterns. Four buzzes means a known object is within 150 cm and requires attention. Two buzzes means something is detected but farther away or unidentified. Complete silence means the path is clear.

Automatic startup on power. The device starts working on its own roughly 50 to 60 seconds after being powered on. No SSH, no keyboard, no screen needed. Plug in the battery and wait.

Bluetooth headphone auto-connect. The headphones pair and connect automatically on boot using a saved device address.


What We Honestly Could Not Complete

The vibration motor occasionally needs a few seconds to become consistent after the system starts. It works correctly but not always instantly.

Battery life was not formally measured. Informal testing showed roughly 3 to 4 hours of use from a dual lithium cell pack but this needs proper testing.

Detection accuracy drops noticeably in low light or dark rooms. The AI model works well under normal indoor lighting but struggles in dim environments.

The system currently speaks in English only. Arabic language output was planned but not implemented within the project timeline.

The camera only covers roughly 62 degrees in front of the cane. There is no side or rear detection.


Hardware Used

Raspberry Pi Zero 2W with 512 MB RAM running at 1 GHz
OV5647 5 megapixel camera connected through the CSI ribbon cable
VL53L0X Time-of-Flight distance sensor connected over I2C
DC eccentric rotating mass vibration motor connected to GPIO 18
Bluetooth headphones connected via PulseAudio
32 GB MicroSD card with Raspberry Pi OS Bookworm 64-bit
Breadboard and female-to-female jumper wires

Total hardware cost: approximately 85 USD


Wiring

VL53L0X Distance Sensor
VIN connects to Physical Pin 1 which is 3.3V power
GND connects to Physical Pin 6 which is ground
SDA connects to Physical Pin 3 which is GPIO 2
SCL connects to Physical Pin 5 which is GPIO 3

Vibration Motor
Signal wire connects to Physical Pin 12 which is GPIO 18
Power wire connects to Physical Pin 2 which is 5V
Ground wire connects to Physical Pin 9 which is GND


Software and Tools Used

Raspberry Pi OS Bookworm 64-bit as the operating system
Python 3.11 as the programming language
Picamera2 and libcamera for camera access
OpenCV DNN module for running the AI model
SSD MobileNet V1 COCO frozen inference graph as the detection model
smbus2 library for reading the distance sensor over I2C
RPi.GPIO library for controlling the vibration motor
espeak-ng for text to speech audio output
PulseAudio for Bluetooth audio routing
systemd for automatic startup management on boot


How to Set Up From Scratch

Step 1. Flash Raspberry Pi OS Bookworm 64-bit to the MicroSD card using Raspberry Pi Imager. Enable SSH in the imager settings before flashing.

Step 2. SSH into the Pi and run the following commands.

sudo apt update && sudo apt upgrade -y

sudo apt install -y python3-opencv python3-picamera2 python3-libcamera espeak-ng i2c-tools

pip3 install smbus2 RPi.GPIO --break-system-packages

Step 3. Enable I2C and camera interfaces.

sudo raspi-config

Go to Interface Options and enable both I2C and Camera. Reboot when prompted.

Step 4. Download the AI model.

mkdir -p /home/pi/model/ssd_mobilenet_v1_coco_2017_11_17
cd /home/pi/model/ssd_mobilenet_v1_coco_2017_11_17

wget http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2017_11_17.tar.gz
tar -xvzf ssd_mobilenet_v1_coco_2017_11_17.tar.gz --strip-components=1

wget -O ssd_mobilenet_v1_coco.pbtxt https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/ssd_mobilenet_v1_coco_2017_11_17.pbtxt

Step 5. Copy the scripts from this repository to /home/pi/ and make them executable.

Step 6. Set up auto-start.

sudo cp smartcane.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable smartcane.service
sudo reboot


Testing the System

To test if the camera is working run this.
rpicam-still --list-cameras

To test if the distance sensor is detected run this.
sudo i2cdetect -y 1
You should see the number 29 appear in the grid output.

To run the main script manually run this.
python3 /home/pi/ai_test_picamera2.py

To check what the system is doing after auto-start run this.
tail -50 /home/pi/smartcane.log

To restart the service manually run this.
sudo systemctl restart smartcane.service


Project Status Summary

Camera object detection is working
Distance measurement is working
Bluetooth audio feedback is working
Vibration motor feedback is working
Auto-start on boot is working
Battery powered headless operation is working
Arabic language audio output is planned for future work
Wider angle camera coverage is planned for future work
Formal battery life testing is pending
Low light performance improvement is planned


Files in This Repository

scripts/ai_test_picamera2.py is the main detection script that handles camera, AI, distance sensor, and audio

scripts/motor_process.py is the independent motor control process that runs separately from the main script

scripts/bt_connect.sh is the Bluetooth headphone auto-connect script

scripts/start_smartcane.sh is the wrapper script that cleans up stuck processes before starting the main script

smartcane.service is the systemd service file for auto-start on boot

docs/ contains the IEEE conference paper written for this project

The AI model files are not included in this repository because they are too large for GitHub. Download instructions are in the setup section above.


Authors

Adeel Ahmad, BS Information Technology Student
Ali Akrama,  BS Information Technology Student
Department of Information Technology


License

This project is open source under the MIT License. You are free to use, modify, and build on it with attribution. If you use this work in academic research please cite the paper available in the docs folder.
