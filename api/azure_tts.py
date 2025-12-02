"""Microsoft Azure Text-to-Speech API integration."""

import hashlib
import os
import requests
from flask import Blueprint, request, jsonify

azure_tts_bp = Blueprint('azure_tts', __name__, url_prefix='/api/azure-tts')

# Azure TTS 配置
# TODO: 用户需要在这里填入自己的 Azure 密钥和区域
AZURE_SPEECH_KEY = "YOUR_AZURE_SPEECH_KEY"  # 替换为您的 Azure 语音服务密钥
AZURE_SPEECH_REGION = "eastasia"  # 替换为您的区域（如 eastasia, westus 等）

# TTS cache directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'azure_tts_cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(text, voice="en-US-JennyNeural", speed=1.0):
    """Generate cache file path based on text, voice and speed."""
    cache_key = f"{text}_{voice}_{speed}"
    file_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{file_hash}.mp3")


def synthesize_speech_azure(text, voice="en-US-JennyNeural", speed=1.0):
    """
    Synthesize speech using Azure TTS API.
    
    Args:
        text: Text to synthesize
        voice: Voice name (e.g., en-US-JennyNeural, en-GB-SoniaNeural)
        speed: Speech speed (0.5 - 2.0)
    
    Returns:
        Audio data in bytes
    """
    # Check cache first
    cache_path = get_cache_path(text, voice, speed)
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()
    
    # Build SSML (Speech Synthesis Markup Language)
    # Speed is represented as a percentage: 1.0 = +0%, 0.8 = -20%, 1.2 = +20%
    speed_percent = int((speed - 1.0) * 100)
    speed_str = f"{speed_percent:+d}%" if speed_percent != 0 else "+0%"
    
    ssml = f"""<speak version='1.0' xml:lang='en-US'>
        <voice name='{voice}'>
            <prosody rate='{speed_str}'>
                {text}
            </prosody>
        </voice>
    </speak>"""
    
    # Azure TTS endpoint
    url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "StudyTracker"
    }
    
    try:
        response = requests.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=10)
        
        if response.status_code == 200:
            audio_data = response.content
            
            # Cache the result
            with open(cache_path, 'wb') as f:
                f.write(audio_data)
            
            return audio_data
        else:
            print(f"Azure TTS error: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        print(f"Azure TTS exception: {e}")
        return None


@azure_tts_bp.route('/synthesize', methods=['POST'])
def synthesize():
    """Synthesize text to speech using Azure TTS."""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        speed = float(data.get('speed', 1.0))
        voice = data.get('voice', 'en-US-JennyNeural')
        
        if not text:
            return jsonify({"ok": False, "error": "text_required"}), 400
        
        # Limit text length
        if len(text) > 5000:
            return jsonify({"ok": False, "error": "text_too_long"}), 400
        
        # Synthesize speech
        audio_data = synthesize_speech_azure(text, voice, speed)
        
        if not audio_data:
            return jsonify({"ok": False, "error": "synthesis_failed"}), 500
        
        # Generate cache URL
        cache_path = get_cache_path(text, voice, speed)
        cache_filename = os.path.basename(cache_path)
        audio_url = f"/static/azure_tts_cache/{cache_filename}"
        
        return jsonify({
            "ok": True,
            "audio_url": audio_url,
            "duration": len(audio_data) / 6000  # Rough estimate in seconds
        })
    
    except Exception as e:
        print(f"Azure TTS synthesis error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@azure_tts_bp.route('/word', methods=['POST'])
def synthesize_word():
    """Synthesize a single word using Azure TTS."""
    try:
        data = request.get_json()
        word = data.get('word', '').strip()
        voice = data.get('voice', 'en-US-JennyNeural')
        
        if not word:
            return jsonify({"ok": False, "error": "word_required"}), 400
        
        # Use normal speed for single words
        audio_data = synthesize_speech_azure(word, voice, speed=1.0)
        
        if not audio_data:
            return jsonify({"ok": False, "error": "synthesis_failed"}), 500
        
        # Generate cache URL
        cache_path = get_cache_path(word, voice, 1.0)
        cache_filename = os.path.basename(cache_path)
        audio_url = f"/static/azure_tts_cache/{cache_filename}"
        
        return jsonify({
            "ok": True,
            "audio_url": audio_url
        })
    
    except Exception as e:
        print(f"Azure TTS word synthesis error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@azure_tts_bp.route('/voices', methods=['GET'])
def list_voices():
    """List available Azure TTS voices."""
    # 常用的英语神经网络语音
    voices = [
        {"name": "en-US-JennyNeural", "desc": "美式英语 - Jenny（女声，温暖友好）", "gender": "Female", "locale": "en-US"},
        {"name": "en-US-AriaNeural", "desc": "美式英语 - Aria（女声，专业）", "gender": "Female", "locale": "en-US"},
        {"name": "en-US-GuyNeural", "desc": "美式英语 - Guy（男声，成熟稳重）", "gender": "Male", "locale": "en-US"},
        {"name": "en-GB-SoniaNeural", "desc": "英式英语 - Sonia（女声，优雅）", "gender": "Female", "locale": "en-GB"},
        {"name": "en-GB-RyanNeural", "desc": "英式英语 - Ryan（男声，专业）", "gender": "Male", "locale": "en-GB"},
        {"name": "en-AU-NatashaNeural", "desc": "澳式英语 - Natasha（女声）", "gender": "Female", "locale": "en-AU"},
    ]
    
    return jsonify({
        "ok": True,
        "voices": voices
    })
