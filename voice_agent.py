import os
import asyncio
import json
import base64
import websockets
import pyaudio
import numpy as np
import speech_recognition as sr
import openwakeword
from openwakeword.model import Model
from faster_whisper import WhisperModel
import edge_tts
import pygame
import torch
import threading
import queue

# 1. Inject PyTorch CUDA libraries
torch_lib_path = os.path.join(os.path.dirname(torch.__file__), "lib")
if os.path.exists(torch_lib_path):
    os.environ["PATH"] = torch_lib_path + os.pathsep + os.environ["PATH"]
    os.add_dll_directory(torch_lib_path)

openwakeword.utils.download_models()

whisper = WhisperModel("base", device="cuda", compute_type="float16")
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

# Background queue for continuous, gapless TTS streaming
speech_queue = queue.Queue()

def tts_worker():
    """Continuously synthesizes and plays sentences as they arrive in the queue"""
    while True:
        text = speech_queue.get()
        if text is None: 
            break
        
        async def _speak():
            communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
            await communicate.save("response.mp3")
            
            pygame.mixer.init()
            pygame.mixer.music.load("response.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            pygame.mixer.music.unload()
            pygame.mixer.quit()
            
            if os.path.exists("response.mp3"):
                os.remove("response.mp3")
                
        asyncio.run(_speak())
        speech_queue.task_done()

# Start the TTS worker thread
threading.Thread(target=tts_worker, daemon=True).start()

async def ask_jarvis(prompt):
    if not os.path.exists("latest_frame.jpg"):
        speech_queue.put("I cannot see the desk right now.")
        return
        
    with open("latest_frame.jpg", "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    try:
        async with websockets.connect("ws://localhost:8000/ws/jarvis") as ws:
            await ws.send(json.dumps({
                "image_base64": img_b64, 
                "prompt": prompt
            }))
            
            current_sentence = ""
            while True:
                try:
                    chunk = await ws.recv()
                    print(chunk, end="", flush=True)
                    current_sentence += chunk
                    
                    # Push to TTS queue immediately upon reaching punctuation
                    if any(p in chunk for p in ['.', '!', '?']):
                        speech_queue.put(current_sentence.strip())
                        current_sentence = ""
                        
                except websockets.ConnectionClosed:
                    if current_sentence.strip():
                        speech_queue.put(current_sentence.strip())
                    break
    except Exception as e:
        speech_queue.put("I am having trouble connecting to the vision server.")

def record_and_transcribe():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for prompt...")
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            return ""
        
    with open("temp.wav", "wb") as f:
        f.write(audio.get_wav_data())
        
    segments, _ = whisper.transcribe("temp.wav", beam_size=5)
    prompt = "".join([segment.text for segment in segments]).strip()
    
    if os.path.exists("temp.wav"):
        os.remove("temp.wav")
        
    return prompt

def listen_for_wake_word():
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16, 
        channels=1, 
        rate=16000, 
        input=True, 
        frames_per_buffer=1280
    )
    
    print("Waiting for wake word ('Hey Jarvis')...")
    
    while True:
        raw_data = stream.read(1280, exception_on_overflow=False)
        pcm = np.frombuffer(raw_data, dtype=np.int16)
        prediction = oww_model.predict(pcm)
        
        if prediction['hey_jarvis'] > 0.5:
            print("\n[Wake Word Detected!]")
            stream.stop_stream()
            
            user_prompt = record_and_transcribe()
            if user_prompt:
                print(f"User: {user_prompt}")
                print("Jarvis: ", end="", flush=True)
                asyncio.run(ask_jarvis(user_prompt))
                
                # Wait for JARVIS to finish speaking all sentences before resuming listening
                speech_queue.join()
                print("\n")
            else:
                print("No speech detected.")
            
            # WIPE internal memory buffers to prevent immediate ghost triggers
            oww_model.reset()
            stream.start_stream()
            
            # DRAIN stale audio frames from the hardware buffer
            if stream.get_read_available() > 0:
                stream.read(stream.get_read_available(), exception_on_overflow=False)
                
            print("\nWaiting for wake word...")

if __name__ == "__main__":
    listen_for_wake_word()