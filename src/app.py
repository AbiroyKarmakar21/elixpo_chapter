import os
import time
import traceback
import io
import wave
import base64
from flask import Flask, request, jsonify, Response, g
from flask_cors import CORS
from loguru import logger
from utility import save_temp_audio, cleanup_temp_file, validate_and_decode_base64_audio, encode_audio_base64
from requestID import reqID
import asyncio
import threading
import subprocess
import logging
from voiceMap import VOICE_BASE64_MAP
import loggerConfig
from server import run_audio_pipeline
import uuid
import multiprocessing as mp
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io




request_queue = None
response_queue = None
worker_process = None

def init_worker():
    """Initialize the worker process"""
    global request_queue, response_queue, worker_process
    from model_server import model_worker
    from model_service import init_model_service
    
    request_queue = mp.Queue()
    response_queue = mp.Queue()
    worker_process = mp.Process(target=model_worker, args=(request_queue, response_queue))
    worker_process.start()
    init_model_service(request_queue, response_queue)

app = Flask(__name__)
CORS(app)

@app.before_request
def before_request():
    g.request_id = reqID()
    g.start_time = time.time()

@app.after_request
def after_request(response):
    process_time = time.time() - g.get('start_time', time.time())
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "endpoints": {
            "GET": "/audio?text=your_text_here&system=optional_system_prompt&voice=optional_voice",
            "POST": "/audio"
        }
    })

@app.route("/audio", methods=["GET", "POST"])
def audio_endpoint():
    request_id = g.request_id
    if request.method == "GET":
        try:
            text = request.args.get("text")
            system = request.args.get("system")
            voice = request.args.get("voice")
            voice_path = None
            if VOICE_BASE64_MAP.get(voice):
                named_voice_path = VOICE_BASE64_MAP.get(voice)
                coded = encode_audio_base64(named_voice_path)
                voice_path = save_temp_audio(coded, request_id, "clone")
            else:
                named_voice_path = VOICE_BASE64_MAP.get("alloy")
                coded = encode_audio_base64(named_voice_path)
                voice_path = save_temp_audio(coded, request_id, "clone")
                

            if not text or not isinstance(text, str) or not text.strip():
                return jsonify({"error": {"message": "Missing required 'text' parameter.", "code": 400}}), 400

            result = asyncio.run(run_audio_pipeline(
                reqID=request_id,
                text=text,
                system_instruction=system,
                voice=voice_path
            ))

            if result["type"] == "audio":
                return Response(
                    result["data"],
                    mimetype="audio/wav",
                    headers={
                        "Content-Disposition": f"inline; filename={request_id}.wav",
                        "Content-Length": str(len(result["data"]))
                    }
                )
            elif result["type"] == "text":
                return jsonify({"text": result["data"], "request_id": request_id})
            else:
                return jsonify({"error": {"message": result.get("message", "Unknown error"), "code": 500}}), 500

        except Exception as e:
            logger.error(f"GET error: {traceback.format_exc()}")
            return jsonify({"error": {"message": str(e), "code": 500}}), 500

    elif request.method == "POST":
        try:
            body = request.get_json(force=True)
            messages = body.get("messages", [])
            if not messages or not isinstance(messages, list):
                return jsonify({"error": {"message": "Missing or invalid 'messages' in payload.", "code": 400}}), 400

            # Parse system and user message
            system_instruction = None
            user_content = None
            for msg in messages:
                if msg.get("role") == "system":
                    for item in msg.get("content", []):
                        if item.get("type") == "text":
                            system_instruction = item.get("text")
                elif msg.get("role") == "user":
                    user_content = msg.get("content", [])

            if not user_content or not isinstance(user_content, list):
                return jsonify({"error": {"message": "Missing or invalid 'content' in user message.", "code": 400}}), 400

            text = None
            voice_name = "alloy"
            voice_b64 = None
            clone_audio_transcript = None
            speech_audio_b64 = None

            for item in user_content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text")
                    elif item.get("type") == "voice":
                        v = item.get("voice", {})
                        if isinstance(v, dict):
                            voice_name = v.get("name", "alloy")
                            if v.get("data"):
                                voice_b64 = v.get("data")
                    elif item.get("type") == "clone_audio_transcript":
                        clone_audio_transcript = item.get("audio_text")
                    elif item.get("type") == "speech_audio":
                        speech_audio_b64 = item.get("audio", {}).get("data")

            if not text or not isinstance(text, str) or not text.strip():
                return jsonify({"error": {"message": "Missing required 'text' in content.", "code": 400}}), 400

            # If both voice_b64 and a non-default voice_name are provided, error
            if voice_b64 and voice_name and voice_name != "alloy":
                return jsonify({"error": {"message": "Provide either 'voice.data' (base64) or 'voice.name', not both.", "code": 400}}), 400

            # Validate and save base64 audio if present
            voice_path = None
            speech_audio_path = None

            if voice_b64:
                try:
                    decoded = validate_and_decode_base64_audio(voice_b64, max_duration_sec=5)
                    voice_path = save_temp_audio(decoded, request_id, "clone")
                except Exception as e:
                    return jsonify({"error": {"message": f"Invalid voice audio: {e}", "code": 400}}), 400
            elif voice_name and not voice_b64:
                try:
                    if VOICE_BASE64_MAP.get(voice_name):
                        named_voice_path = VOICE_BASE64_MAP.get(voice_name)
                        coded = encode_audio_base64(named_voice_path)
                        voice_path = save_temp_audio(coded, request_id, "clone")
                    else:
                        named_voice_path = VOICE_BASE64_MAP.get("alloy")
                        coded = encode_audio_base64(named_voice_path)
                        voice_path = save_temp_audio(coded, request_id, "clone")
                except Exception as e:
                    return jsonify({"error": {"message": f"Invalid voice name: {e}", "code": 400}}), 400
            else:
                named_voice_path = VOICE_BASE64_MAP.get("alloy")
                coded = encode_audio_base64(named_voice_path)
                voice_path = save_temp_audio(coded, request_id, "clone")

            if speech_audio_b64:
                try:
                    decoded = validate_and_decode_base64_audio(speech_audio_b64, max_duration_sec=60)
                    speech_audio_path = save_temp_audio(decoded, request_id, "speech")
                except Exception as e:
                    return jsonify({"error": {"message": f"Invalid speech_audio: {e}", "code": 400}}), 400

            # If voice_path is present, ignore voice_name param

            result = asyncio.run(run_audio_pipeline(
                reqID=request_id,
                text=text,
                voice=voice_path,
                synthesis_audio_path=speech_audio_path,
                clone_audio_transcript=clone_audio_transcript,
                system_instruction=system_instruction,
            ))

            if result["type"] == "audio":
                return Response(
                    result["data"],
                    mimetype="audio/wav",
                    headers={
                        "Content-Disposition": f"inline; filename={request_id}.wav",
                        "Content-Length": str(len(result["data"]))
                    }
                )
            elif result["type"] == "text":
                return jsonify({"text": result["data"], "request_id": request_id})
            else:
                return jsonify({"error": {"message": result.get("message", "Unknown error"), "code": 500}}), 500

        except Exception as e:
            logger.error(f"POST error: {traceback.format_exc()}")
            return jsonify({"error": {"message": str(e), "code": 500}}), 500
        finally:
            cleanup_temp_file(request_id)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": {"message": str(e), "code": 400}}), 400

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return jsonify({"error": {"message": "Internal server error", "code": 500}}), 500

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    init_worker()
    host = "0.0.0.0"
    port = 8000
    logger.info(f"Starting Elixpo Audio API Server at {host}:{port}")

    try:
        # Use Flask's built-in server with threading support
        app.run(host=host, port=port, debug=False, threaded=True)
    finally:
        # Clean up worker process
        if worker_process and worker_process.is_alive():
            request_queue.put("STOP")
            worker_process.join(timeout=5)
            if worker_process.is_alive():
                worker_process.terminate()