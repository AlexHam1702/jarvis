import cv2
import base64
import re
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ollama import AsyncClient
import windows_tools
import memory_tools
app = FastAPI()
client = AsyncClient()

class VisionEvent(BaseModel):
    image_base64: str = ""
    prompt: str

@app.get("/")
async def mobile_app():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
        <style>
            body { background: #111; color: #fff; font-family: sans-serif; padding: 20px; text-align: center; }
            button { background: #00ff00; color: #000; border: none; padding: 30px; font-size: 24px; border-radius: 50%; width: 200px; height: 200px; margin-top: 40px; cursor: pointer; }
            #log { margin-top: 30px; font-size: 18px; color: #aaa; line-height: 1.5; }
        </style>
    </head>
    <body>
        <h2>JARVIS Mobile</h2>
        <button id="talk">Tap to Speak</button>
        <p id="log">Status: Ready</p>
        
        <script>
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            let ws;

            function connect() {
                ws = new WebSocket(`${protocol}//${window.location.host}/ws/jarvis`);
                
                ws.onopen = () => {
                    document.getElementById('log').innerText = "Status: Connected";
                };

                ws.onmessage = (event) => {
                    document.getElementById('log').innerText = "JARVIS: " + event.data;
                    const utterance = new SpeechSynthesisUtterance(event.data);
                    speechSynthesis.speak(utterance);
                };

                ws.onclose = () => {
                    document.getElementById('log').innerText = "Status: Disconnected. Reconnecting...";
                    setTimeout(connect, 2000);
                };
            }

            connect();

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();

            document.getElementById('talk').onclick = () => {
                document.getElementById('log').innerText = "Listening...";
                recognition.start();
            };

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                document.getElementById('log').innerText = "You: " + text;
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({prompt: text, image_base64: ""}));
                }
            };

            recognition.onerror = (event) => {
                document.getElementById('log').innerText = "Mic error: " + event.error;
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

@app.websocket("/ws/jarvis")
async def jarvis_stream(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            event = VisionEvent(**data)
            prompt = event.prompt.strip()
            prompt_lower = prompt.lower()

            # --- 1. TOOL: CHANGE VOLUME ---
            volume_match = re.search(r'(?:volume.*?(\d+)|(\d+).*?volume)', prompt_lower)
            if "volume" in prompt_lower and volume_match:
                level = int(volume_match.group(1) or volume_match.group(2))
                windows_tools.set_volume(level)
                await websocket.send_text(f"Setting volume to {level} percent.")
                continue

            # --- 2. TOOL: LAUNCH APPLICATION ---
            open_match = re.match(r'^(?:open|launch|start)\s+([a-zA-Z0-9_\- ]+)', prompt_lower)
            if open_match:
                target_app = open_match.group(1).strip()
                target_app = re.sub(r'^(the|an?)\s+', '', target_app).strip()
                windows_tools.launch_application(target_app)
                await websocket.send_text(f"Opening {target_app} now.")
                continue

            # --- 3. TOOL: WEB SEARCH ---
            if prompt_lower.startswith("search "):
                site = None
                query = prompt_lower.replace("search ", "", 1).strip()
                
                site_for_match = re.match(r'^([a-z0-9\.]+)\s+for\s+(.+)$', query)
                if site_for_match:
                    site = site_for_match.group(1)
                    query = site_for_match.group(2)
                else:
                    query_on_match = re.match(r'^(.+)\s+on\s+([a-z0-9\.]+)$', query)
                    if query_on_match:
                        query = query_on_match.group(1)
                        site = query_on_match.group(2)
                        
                windows_tools.search_web(query, site)
                await websocket.send_text(f"Searching for {query}.")
                continue

            # --- 4. TOOL: SMART HOME CONTROL ---
            if re.search(r'\b(dehumidifier|woods)\b', prompt_lower) and re.search(r'\b(on|off)\b', prompt_lower):
                state = re.search(r'\b(on|off)\b', prompt_lower).group(1)
                windows_tools.toggle_dehumidifier(state)
                await websocket.send_text(f"I have turned the dehumidifier {state}.")
                continue

            # --- 5. TOOL: MEDIA CONTROLS ---
            media_match = re.search(r'\b(pause|play|skip|next|previous|replay|last)\b', prompt_lower)
            if media_match and ("song" in prompt_lower or "music" in prompt_lower or "track" in prompt_lower or len(prompt_lower.split()) < 4):
                action_word = media_match.group(1)
                if action_word in ["skip", "next"]:
                    windows_tools.control_media("next")
                    await websocket.send_text("Skipping to the next track.")
                elif action_word in ["previous", "replay", "last"]:
                    windows_tools.control_media("prev")
                    await websocket.send_text("Restarting track.")
                else:
                    windows_tools.control_media("play_pause")
                    await websocket.send_text("Toggling playback.")
                continue

            # --- TOOL: PERSISTENT MEMORY ---
            if prompt_lower.startswith("remember that "):
                fact_to_save = prompt.replace("Remember that ", "", 1).strip()
                memory_tools.remember_fact(fact_to_save)
                await websocket.send_text(f"I've committed that to my memory and pushed it to GitHub.")
                continue

            # --- TOOL: READ OUTLOOK CALENDAR ---
            if any(phrase in prompt_lower for phrase in ["what's on my calendar", "check my schedule", "upcoming meetings", "what do i have"]):
                await websocket.send_text("Checking your calendar...")
                agenda_summary = windows_tools.get_upcoming_events(days_ahead=3)
                await websocket.send_text(agenda_summary)
                continue

            
            # --- TOOL: OUTLOOK CALENDAR PARSER ---
            if any(keyword in prompt_lower for keyword in ["schedule", "calendar", "appointment", "meeting", "reminder"]):
                await websocket.send_text("Parsing your calendar request...")
                
                # Construct a precise parsing prompt with current date context
                parsing_prompt = f"""
                Current date and time: Friday, September 4, 2026, 9:36 PM.
                Extract calendar event details from this user request: "{prompt}"
                
                You must return ONLY a raw JSON object with these exact keys:
                - "subject": string (title of the event)
                - "start_time": string formatted strictly as "YYYY-MM-DD HH:MM" in 24-hour format
                - "duration_minutes": integer (default to 60 if not specified)
                - "body": string (any extra notes, or empty string "")
                
                Do not include markdown code blocks (like ```json), commentary, or any text outside the JSON object.
                """
                
                try:
                    # Query DeepSeek-R1 for structured extraction
                    raw_response = ""
                    async for chunk in await client.chat(
                        model='deepseek-r1:8b',
                        messages=[{'role': 'user', 'content': parsing_prompt}],
                        stream=True
                    ):
                        content = chunk.message.content if hasattr(chunk, 'message') else chunk['message']['content']
                        if content:
                            raw_response += content
                    
                    # Strip DeepSeek's <think> tags and clean the string
                    clean_text = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
                    # Remove markdown code block markers if the model included them anyway
                    clean_text = re.sub(r'```(?:json)?', '', clean_text).strip()
                    
                    # Parse the JSON payload
                    event_data = json.loads(clean_text)
                    
                    subject = event_data.get("subject", "JARVIS Meeting")
                    start_time = event_data.get("start_time")
                    duration = int(event_data.get("duration_minutes", 60))
                    body = event_data.get("body", "")
                    
                    # Execute local Outlook tool
                    success = windows_tools.add_calendar_event(subject, start_time, duration, body)
                    
                    if success:
                        await websocket.send_text(f"Successfully scheduled '{subject}' for {start_time}.")
                    else:
                        await websocket.send_text("I understood the request, but failed to write it to Outlook.")
                        
                except Exception as e:
                    print(f"[Calendar Parse Error]: {e} | Raw text was: {raw_response}")
                    await websocket.send_text("I couldn't parse the date and time for that event. Try phrasing it with a clear date and time.")
                continue

            

            # --- TOOL: MORNING BRIEFING ROUTINE ---
            if "good morning" in prompt_lower or "morning briefing" in prompt_lower:
                await websocket.send_text("Compiling your morning briefing, sir...")
                
                # 1. Gather live backend data
                vitals = windows_tools.get_system_status()
                weather = windows_tools.get_weather()
                agenda = windows_tools.get_todays_agenda()
                
                # 2. Craft the cinematic persona prompt
                briefing_prompt = f"""
                You are JARVIS, a sophisticated personal AI assistant. Synthesize these live data points into a crisp, professional, and slightly witty morning briefing script:
                - System Vitals: {vitals}
                - Weather: {weather}
                - Today's Outlook Agenda: {agenda}
                
                Speak directly to the user. Do not include markdown code blocks or meta-commentary, just output the spoken words.
                """
                
                try:
                    full_briefing = ""
                    async for chunk in await client.chat(
                        model='deepseek-r1:8b',
                        messages=[{'role': 'user', 'content': briefing_prompt}],
                        stream=True
                    ):
                        content = chunk.message.content if hasattr(chunk, 'message') else chunk['message']['content']
                        if content:
                            full_briefing += content
                            
                    # Strip DeepSeek's internal reasoning block
                    clean_briefing = re.sub(r'<think>.*?</think>', '', full_briefing, flags=re.DOTALL).strip()
                    
                    await websocket.send_text(clean_briefing)
                except Exception as e:
                    await websocket.send_text(f"Good morning. Systems are operational, but I encountered an error compiling your full briefing: {e}")
                continue

            # --- 6. GENERAL REASONING (Fallback to DeepSeek-R1) NO OTHER TOOLS BEYOND THIS POINT ---
            messages = [{'role': 'user', 'content': prompt}]
                
            try:
                full_reply = ""
                async for chunk in await client.chat(
                    model='deepseek-r1:8b',
                    messages=messages,
                    stream=True
                ):
                    content = chunk.message.content if hasattr(chunk, 'message') else chunk['message']['content']
                    if content:
                        full_reply += content
                
                # DeepSeek-R1 outputs internal thoughts in <think>...</think> tags.
                # This regex strips them out so JARVIS only says the final response.
                clean_reply = re.sub(r'<think>.*?</think>', '', full_reply, flags=re.DOTALL).strip()
                
                if clean_reply:
                    await websocket.send_text(clean_reply)
                else:
                    await websocket.send_text("I processed your request.")
            except Exception as e:
                await websocket.send_text(f"Error processing query: {str(e)}")

    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)