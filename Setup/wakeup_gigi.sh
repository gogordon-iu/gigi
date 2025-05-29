cd /home/orangepi/Code/gigi
chmod +x activate_environment.sh
./activate_environment.sh
source venv/bin/activate
cd Character
python wakeUp.py        # exec keeps service alive
