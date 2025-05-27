# virtual environment
cd ../..
# change ownership, so does not need sudo
sudo chown -R orangepi:orangepi gigi/
cd gigi
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

cd Assets
mkdir recorded_speech

# set speaker volume
amixer -c 2 set PCM 80%
