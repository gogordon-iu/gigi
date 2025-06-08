#!/bin/bash

export DISPLAY=:0
export XAUTHORITY=/home/orangepi/.Xauthority

# Prevent screen blanking
xset s off
xset -dpms
xset s noblank

cd /home/orangepi/Code/gigi
chmod +x activate_environment.sh
./activate_environment.sh
source venv/bin/activate
cd Character
python wakeUp.py        # exec keeps service alive
