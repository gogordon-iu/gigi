# set git
git config --global user.name "gigi"
git config --global user.email "gigi@iu.edu"

# Connect to the appropriate wifi
# nmcli dev wifi connect "MIGO" password "your_password"


# general python
sudo apt update
sudo apt install python3 python3-venv python3-pip -y

# audio
sudo apt install pocketsphinx python3-pocketsphinx -y
sudo apt install portaudio19-dev -y

# motors
sudo apt-get install -y i2c-tools gpiod libgpiod-dev
sudo groupadd gpio
sudo chown root:gpio /dev/gpiochip0
sudo chmod 660 /dev/gpiochip0
sudo chmod 666 /dev/i2c-0 /dev/i2c-1 /dev/i2c-2
sudo usermod -aG gpio orangepi
sudo usermod -aG i2c orangepi


# video
sudo add-apt-repository ppa:mc3man/mpv-tests
sudo apt update
sudo apt install mpv
# Open this file:
#/home/orangepi/Code/gigi/venv/lib/python3.10/site-packages/mpv.py
#Go to line ~1339, and replace:
#if self.mpv_version_tuple >= (0, 38, 0):
#with:
#if False:

# screen
sudo rm -rf LCD-show
cd
git clone https://github.com/goodtft/LCD-show.git
chmod -R 755 LCD-show
cd LCD-show/
sudo ./LCD7C-show

# Setup wake up and associated files
cd ~/Code/gigi/
chmod +x activate_environment.sh
