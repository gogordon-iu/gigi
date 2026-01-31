#source venv/bin/activate
sudo -S <<< 'orangepi' chown root:gpio /dev/gpiochip0
sudo -S <<< 'orangepi' chmod 660 /dev/gpiochip0
