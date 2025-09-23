from nix.models.TTS import NixTTSInference
from nix.tokenizers.tokenizer_en import NixTokenizerEN
import numpy as np
import subprocess
import re
import atexit

# Initialize Nix-TTS
nix = NixTTSInference(model_dir="/home/orangepi/Code/gigi/Resources/nix/models/")

# Input paragraph
text = ("Hey, Gowtham, how are you doing today? It is nice to see you again. "
        "How is your family? I hope they are doing well.")

# Split into sentences
sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', text) if s.strip()]

# Launch a single SoX process in raw→alsa mode
sox_cmd = [
    'sox',
    '-t', 'raw',
    '-r', '22050',
    '-c', '2',
    '-e', 'signed-integer',
    '-b', '16',
    '-',                # stdin raw PCM
    '-t', 'alsa', 'hw:2,0'  # output device
]
proc = subprocess.Popen(sox_cmd, stdin=subprocess.PIPE)
atexit.register(lambda: proc.stdin.close() or proc.wait())

for sentence in sentences:
    print(f"Speaking: {sentence}")

    # Tokenize & infer
    c, c_length, _ = nix.tokenizer([sentence])
    xw = nix.vocalize(c, c_length)[0, 0].astype(np.float32)

    # Mono→stereo
    stereo = np.stack([xw, xw], axis=-1)

    # 16-bit PCM
    pcm = (stereo * 32767).astype(np.int16).tobytes()

    # Stream into the same SoX stdin (no new fork)
    proc.stdin.write(pcm)
    proc.stdin.flush()

# When your script exits, the atexit handler will close stdin & wait on SoX.
