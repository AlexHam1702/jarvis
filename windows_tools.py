
import base64
import os
import subprocess
import webbrowser
import urllib.parse
import pythoncom
import cv2
from pycaw.pycaw import AudioUtilities
import tinytuya
import win32api
import win32com.client
import requests
import win32com.client
from datetime import datetime, timedelta
import psutil

def get_system_status() -> str:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    battery_status = f", Battery at {battery.percent}%" if battery else ""

    return f"CPU load is at {cpu} percent, memory usage is at {memory} percent{battery_status}."

def capture_desk_frame():
    """Takes a single picture from the PC's default webcam and encodes it to base64."""
    cap = cv2.VideoCapture(0) # 0 is usually the default USB/built-in webcam
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("[JARVIS Error]: Failed to grab webcam frame.")
        return None
        
    # Compress to JPEG and encode to base64 string
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buffer).decode('utf-8')
    
def get_weather() -> str:
    """Fetches real-time weather using Open-Meteo (No API key required)."""
    try:
        # Coordinates configured for the Paris / Ile-de-France region
        url = "https://api.open-meteo.com/v1/forecast?latitude=48.80&longitude=2.43&current=temperature_2m,weather_code"
        res = requests.get(url, timeout=3).json()
        temp = res['current']['temperature_2m']
        return f"The current outside temperature is {temp} degrees Celsius."
    except Exception:
        return "Weather service currently unavailable."

def get_todays_agenda() -> str:
    """Pulls today's events from the local Outlook desktop application."""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        
        today = datetime.now().date()
        agenda = []
        for item in items:
            try:
                item_date = datetime(item.Start.year, item.Start.month, item.Start.day).date()
                if item_date == today:
                    time_str = item.Start.strftime("%H:%M")
                    agenda.append(f"{item.Subject} at {time_str}")
            except Exception:
                continue
        return ", ".join(agenda) if agenda else "No meetings or events scheduled for today."
    except Exception:
        return "Could not load Outlook calendar items."

def get_upcoming_events(days_ahead: int = 7) -> str:
    """Reads upcoming appointments from the local Outlook desktop app."""
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar
        
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        
        now = datetime.now()
        future_limit = now + timedelta(days=days_ahead)
        
        # Format dates for Outlook MAPI filtering
        filter_str = f"[Start] >= '{now.strftime('%m/%d/%Y %H:%M')}' AND [Start] <= '{future_limit.strftime('%m/%d/%Y %H:%M')}'"
        restricted_items = items.Restrict(filter_str)
        
        event_list = []
        for item in restricted_items:
            try:
                start_time = item.Start.strftime("%A, %B %d at %H:%M")
                event_list.endswith
                event_list.append(f"- {item.Subject} on {start_time}")
            except Exception:
                continue
                
        if not event_list:
            return f"You have no upcoming events scheduled for the next {days_ahead} days."
            
        return "Here are your upcoming events:\n" + "\n".join(event_list)
    except Exception as e:
        return f"Could not read Outlook calendar: {e}"
    finally:
        pythoncom.CoUninitialize()

def add_calendar_event(subject: str, start_time_str: str, duration_minutes: int = 60, body: str = ""):
    """Creates an appointment in the local Windows Outlook desktop app safely."""
    # Initialize COM for this specific thread (fixes async thread dropouts)
    pythoncom.CoInitialize()
    try:
        # Use DispatchEx to force a fresh background instance if needed, 
        # or fall back to standard Dispatch if Outlook is already open.
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception:
            outlook = win32com.client.DispatchEx("Outlook.Application")
            
        appointment = outlook.CreateItem(1)  # 1 = olAppointmentItem
        
        appointment.Subject = subject
        appointment.Start = start_time_str
        appointment.Duration = duration_minutes
        appointment.Body = body
        
        appointment.Save()
        print(f"[JARVIS]: Successfully added '{subject}' to Outlook calendar for {start_time_str}.")
        return True
    except Exception as e:
        print(f"[JARVIS Error]: Outlook integration failed: {e}")
        return False
    finally:
        # Always uninitialize COM cleanly when done
        pythoncom.CoUninitialize()

# Windows Virtual-Key Codes for Media
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_EXTENDEDKEY = 0x0001

def control_media(action: str):
    """Simulates global Windows media key presses."""
    if action == "play_pause":
        win32api.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY, 0)
        print("[JARVIS]: Media play/pause triggered.")
    elif action == "next":
        win32api.keybd_event(VK_MEDIA_NEXT_TRACK, 0, KEYEVENTF_EXTENDEDKEY, 0)
        print("[JARVIS]: Media next track triggered.")
    elif action == "prev":
        win32api.keybd_event(VK_MEDIA_PREV_TRACK, 0, KEYEVENTF_EXTENDEDKEY, 0)
        print("[JARVIS]: Media previous track triggered.")

# Replace these placeholders with the values from your devices.json
DEHUMIDIFIER_ID = "bf102fc8f2d338afefrhan"
DEHUMIDIFIER_IP = "192.168.1.166"
DEHUMIDIFIER_KEY = "'(hz(6/^vPp2e!UR"

def toggle_dehumidifier(state: str):
    """Turns the Wood's dehumidifier on or off over the local network."""
    # Initialize the Tuya Device (Version 3.3 or 3.4 is standard)
    d = tinytuya.Device(
        dev_id=DEHUMIDIFIER_ID, 
        address=DEHUMIDIFIER_IP, 
        local_key=DEHUMIDIFIER_KEY, 
        version=3.4
    )
    
    # Your status dump confirmed the power channel is '1'
    POWER_DPS = '1' 
    
    if state == "on":
        d.set_value(POWER_DPS, True)
        print("[JARVIS]: Dehumidifier powered ON.")
    elif state == "off":
        d.set_value(POWER_DPS, False)
        print("[JARVIS]: Dehumidifier powered OFF.")

def set_volume(level: int):
    """Sets the Windows master volume to a specific percentage (0-100)"""
    # 1. Get the default audio device (speakers/headphones)
    device = AudioUtilities.GetSpeakers()
    
    # 2. Access the volume controller natively (new pycaw API)
    volume = device.EndpointVolume
    
    # 3. Ensure the audio is not muted
    volume.SetMute(0, None)
    
    # 4. Set the new volume (scalar accepts a float from 0.0 to 1.0)
    scalar_level = max(0, min(level, 100)) / 100.0
    volume.SetMasterVolumeLevelScalar(scalar_level, None)
    
    print(f"[JARVIS]: Volume set to {level}%")

def search_web(query: str, site: str = None):
    """Opens the default browser (Chrome) and performs a URL search."""
    encoded_query = urllib.parse.quote(query)
    
    if site and "youtube" in site.lower():
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
    elif site and "reddit" in site.lower():
        url = f"https://www.reddit.com/search/?q={encoded_query}"
    else:
        # Default to Google; append 'site:example.com' if a specific site is requested
        if site:
            encoded_query += f"+site%3A{urllib.parse.quote(site)}"
        url = f"https://www.google.com/search?q={encoded_query}"
        
    print(f"[JARVIS]: Searching for '{query}'...")
    webbrowser.open(url)

def launch_application(app_name: str):
    """Dynamically searches the Start Menu and launches any installed Windows app"""
    print(f"[JARVIS]: Attempting to open raw target '{app_name}'...")
    
    # 1. Sanitize the LLM output (remove ".exe" and extra spaces)
    clean_name = app_name.lower().replace(".exe", "").replace("app", "").strip()
    
    # 2. Hardcoded fallback for common apps using Windows Registry aliases
    system_apps = {
        "notepad": "notepad",
        "calculator": "calc",
        "chrome": "chrome",
        "spotify": "spotify",
        "discord": "discord",
        "explorer": "explorer",
        "edge": "msedge",
        "outlook": "outlook"
    }
    
    if clean_name in system_apps:
        try:
            # os.system uses the native command prompt to query the App Paths registry
            os.system(f'start {system_apps[clean_name]}')
            print(f"[JARVIS]: Successfully launched {clean_name} via registry.")
            return
        except Exception as e:
            print(f"[JARVIS]: Registry launch failed: {e}")

    # 3. Dynamic Start Menu Search for custom software (e.g. Games, Steam apps)
    ps_command = f'Get-StartApps "*{clean_name}*" | Select-Object -ExpandProperty AppID -First 1'
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command], 
            capture_output=True, 
            text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        app_id = result.stdout.strip()
        
        if app_id:
            print(f"[JARVIS]: Found AppID: {app_id}")
            # explorer shell securely launches modern Windows 10/11 UWP Apps
            os.system(f'explorer "shell:AppsFolder\\{app_id}"')
        else:
            print(f"[JARVIS]: Not found in Start Menu. Attempting raw system start...")
            os.system(f'start {clean_name}')
            
    except Exception as e:
        print(f"[JARVIS Error]: Failed to launch {app_name}: {e}")