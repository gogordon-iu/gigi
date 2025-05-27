import subprocess
import re
import sys

def run_command(cmd):
    return subprocess.check_output(cmd, shell=True, text=True)

def find_usb_audio_card():
    output = run_command("aplay -l")
    cards = []
    for line in output.splitlines():
        if "card" in line.lower() and "usb" in line.lower():
            match = re.search(r"card (\d+):", line)
            if match:
                card_num = int(match.group(1))
                cards.append(card_num)
    return cards

def find_volume_control(card_num):
    output = run_command(f"amixer -c {card_num} scontrols")
    # Search for common playback controls
    for line in output.splitlines():
        match = re.search(r"Simple mixer control '([^']+)'", line)
        if match:
            control = match.group(1)
            # Return the first control that seems to be an output
            if control.lower() in ['pcm', 'master', 'speaker', 'headphone']:
                return control
    return None

def set_volume(card_num, control, volume_percent=80):
    print(f"Setting {control} on card {card_num} to {volume_percent}%")
    subprocess.call(f"amixer -c {card_num} set '{control}' {volume_percent}%", shell=True)

def set_speaker_volume(volume_percent=80):
    cards = find_usb_audio_card()
    if not cards:
        print("No USB audio cards found.")
        return

    for card in cards:
        control = find_volume_control(card)
        if control:
            set_volume(card, control, volume_percent=volume_percent)
            return

    print("No suitable volume control found on USB audio cards.")

if __name__ == "__main__":
    volume = 80
    if len(sys.argv) > 1:
        volume = int(sys.argv[1])
    set_speaker_volume(volume_percent=volume)
