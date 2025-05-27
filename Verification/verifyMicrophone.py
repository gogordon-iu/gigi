import speech_recognition as sr

def list_microphones():
    """
    List all available microphone devices.
    """
    mic_list = sr.Microphone.list_microphone_names()
    return mic_list

def get_usb_microphone(mic_list):
    try:
        usb_device = [(i, m) for i, m in enumerate(mic_list) if "USB" in m][0]
        return usb_device
    except IndexError:
        print("No USB microphone found.")
        return None

def recognize_speech_from_microphone(mic_index):
    """
    Listen to speech from the specified microphone and transcribe it.
    """
    recognizer = sr.Recognizer()
    with sr.Microphone(device_index=mic_index) as source:
        print("Adjusting for ambient noise... Please wait.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening for speech...")

        try:
            audio = recognizer.listen(source, timeout=10)
            print("Processing speech...")
            text = recognizer.recognize_sphinx(audio)
            print(f"Recognized speech: {text}")
        except sr.WaitTimeoutError:
            print("No speech detected within the timeout period.")
        except sr.UnknownValueError:
            print("Speech was unclear or not recognized.")
        except sr.RequestError as e:
            print(f"Error with the speech recognition engine: {e}")

if __name__ == "__main__":
    print("Scanning for available microphones...")
    microphones = list_microphones()

    if not microphones:
        print("No microphones detected. Please connect one and try again.")
    else:
        print("Available microphones:")
        for idx, mic in enumerate(microphones):
            print(f"{idx}: {mic}")
        
        # Use the first available microphone
        selected_mic = get_usb_microphone(microphones)
        selected_mic_index = selected_mic[0]
        print(f"Using microphone: {microphones[selected_mic_index]}")

        # Start listening and transcribing speech
        recognize_speech_from_microphone(selected_mic_index)
