"""Text-to-Speech API using iFlytek TTS service."""

import hashlib
import hmac
import base64
import json
import time
import os
from datetime import datetime
from urllib.parse import urlencode
from flask import Blueprint, request, jsonify, send_file
import websocket
import ssl

tts_bp = Blueprint('tts', __name__, url_prefix='/api/tts')

# iFlytek API credentials
APPID = "b445c79c"
API_KEY = "6e605bfcd297f9de99bacd0d62a5e174"
API_SECRET = "MDU3NTEyMmY1MWUxYjhjNjFiNTAwMWY1"

# TTS cache directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'tts_cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(text, speed=1.0, voice="catherine"):
    """Generate cache file path based on text, speed and voice."""
    cache_key = f"{text}_{speed}_{voice}"
    file_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{file_hash}.mp3")


def generate_auth_url():
    """Generate iFlytek WebSocket authentication URL."""
    host = "tts-api.xfyun.cn"
    path = "/v2/tts"
    
    # Generate RFC1123 format timestamp
    now = datetime.now()
    date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Build signature string
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    
    # Calculate signature
    signature_sha = hmac.new(
        API_SECRET.encode('utf-8'),
        signature_origin.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')
    
    # Build authorization header
    authorization_origin = f'api_key="{API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
    
    # Build URL
    params = {
        "authorization": authorization,
        "date": date,
        "host": host
    }
    
    return f"wss://{host}{path}?{urlencode(params)}"


def synthesize_speech(text, speed=1.0, voice="catherine"):
    """
    Synthesize speech using iFlytek TTS API.
    
    Args:
        text: Text to synthesize
        speed: Speech speed (0.5 - 2.0)
        voice: Voice name (catherine for English female)
    
    Returns:
        Audio data in bytes
    """
    # Check cache first
    cache_path = get_cache_path(text, speed, voice)
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()
    
    # Generate WebSocket URL
    ws_url = generate_auth_url()
    
    # Prepare request parameters
    request_params = {
        "common": {
            "app_id": APPID
        },
        "business": {
            "aue": "lame",  # MP3 format
            "auf": "audio/L16;rate=16000",
            "vcn": voice,
            "speed": int(speed * 50),  # Convert to iFlytek scale (0-100)
            "volume": 50,
            "pitch": 50,
            "bgs": 0,
            "tte": "utf8"
        },
        "data": {
            "status": 2,
            "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
        }
    }
    
    # Collect audio data
    audio_data = bytearray()
    
    def on_message(ws, message):
        response = json.loads(message)
        code = response.get("code")
        
        if code != 0:
            print(f"TTS error: {response.get('message')}")
            ws.close()
            return
        
        # Extract audio data
        audio = response.get("data", {}).get("audio")
        if audio:
            audio_data.extend(base64.b64decode(audio))
        
        # Check if synthesis is complete
        if response.get("data", {}).get("status") == 2:
            ws.close()
    
    def on_error(ws, error):
        print(f"WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        pass
    
    def on_open(ws):
        ws.send(json.dumps(request_params))
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    
    # Run WebSocket (blocking)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    
    # Cache the result
    if audio_data:
        with open(cache_path, 'wb') as f:
            f.write(audio_data)
    
    return bytes(audio_data)


@tts_bp.route('/synthesize', methods=['POST'])
def synthesize():
    """Synthesize text to speech."""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        speed = float(data.get('speed', 1.0))
        
        if not text:
            return jsonify({"ok": False, "error": "text_required"}), 400
        
        # Limit text length
        if len(text) > 5000:
            return jsonify({"ok": False, "error": "text_too_long"}), 400
        
        # Synthesize speech
        audio_data = synthesize_speech(text, speed)
        
        if not audio_data:
            return jsonify({"ok": False, "error": "synthesis_failed"}), 500
        
        # Generate cache URL
        cache_path = get_cache_path(text, speed, voice="catherine")
        cache_filename = os.path.basename(cache_path)
        audio_url = f"/static/tts_cache/{cache_filename}"
        
        return jsonify({
            "ok": True,
            "audio_url": audio_url,
            "duration": len(audio_data) / 4000  # Rough estimate in seconds
        })
    
    except Exception as e:
        print(f"TTS synthesis error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@tts_bp.route('/word', methods=['POST'])
def synthesize_word():
    """Synthesize a single word (optimized for quick playback)."""
    try:
        data = request.get_json()
        word = data.get('word', '').strip()
        
        if not word:
            return jsonify({"ok": False, "error": "word_required"}), 400
        
        # Use faster speed for single words
        audio_data = synthesize_speech(word, speed=1.0)
        
        if not audio_data:
            return jsonify({"ok": False, "error": "synthesis_failed"}), 500
        
        # Generate cache URL
        cache_path = get_cache_path(word, 1.0, voice="catherine")
        cache_filename = os.path.basename(cache_path)
        audio_url = f"/static/tts_cache/{cache_filename}"
        
        return jsonify({
            "ok": True,
            "audio_url": audio_url
        })
    
    except Exception as e:
        print(f"TTS word synthesis error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
