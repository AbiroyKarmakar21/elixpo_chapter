from quart import Quart, request, jsonify, Response
from quart_cors import cors
import asyncio
import time
import random
import logging
import sys
import uuid
from searchPipeline import run_elixposearch_pipeline
import hypercorn.asyncio
import json
from hypercorn.config import Config
from getYoutubeDetails import get_youtube_transcript
from collections import deque
from datetime import datetime, timedelta

app = Quart(__name__)
app = cors(app, allow_origin="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', stream=sys.stdout)
app.logger.setLevel(logging.INFO)

# Increased concurrency settings
request_queue = asyncio.Queue(maxsize=100) 
processing_semaphore = asyncio.Semaphore(15)  
active_requests = {}

# Global stats for monitoring
global_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "start_time": time.time(),
    "last_request_time": None,
    "avg_processing_time": 0.0
}

transcript_rate_limit = {
    "window": 60, 
    "limit": 20,
    "requests": deque()
}


class RequestTask:
    def __init__(self, request_id: str, user_query: str, request_type: str, event_id: str = None):
        self.request_id = request_id
        self.user_query = user_query
        self.request_type = request_type
        self.event_id = event_id
        self.result_future = asyncio.Future()
        self.timestamp = time.time()
        self.start_processing_time = None

async def process_request_worker():
    """Background worker for NON-SSE requests only"""
    while True:
        try:
            task = await asyncio.wait_for(request_queue.get(), timeout=1.0)
            
            if task.request_type == 'sse':
                task.result_future.set_exception(Exception("SSE requests should not be queued"))
                continue
            
            async with processing_semaphore:
                task.start_processing_time = time.time()
                app.logger.info(f"Processing request {task.request_id} - {task.request_type}")
                active_requests[task.request_id] = task
                
                try:
                    # For JSON/Chat, collect final result
                    final_result_content = []
                    # Unpack user_query and user_image for the pipeline
                    uq, ui = task.user_query if isinstance(task.user_query, tuple) else (task.user_query, None)
                    async for chunk in run_elixposearch_pipeline(uq, ui, event_id=None):
                        lines = chunk.splitlines()
                        event_type = None
                        data_lines = []

                        for line in lines:
                            if line.startswith("event:"):
                                event_type = line.replace("event:", "").strip()
                            elif line.startswith("data:"):
                                data_lines.append(line.replace("data:", "").strip())

                        data_text = "\n".join(data_lines)
                        if data_text and event_type in ["final", "final-part"]:
                            final_result_content.append(data_text)
                    
                    final_response = "\n".join(final_result_content).strip()
                    if not final_response:
                        final_response = "No results found"
                    
                    task.result_future.set_result(final_response)
                    
                    # Update success stats
                    processing_time = time.time() - task.start_processing_time
                    global_stats["successful_requests"] += 1
                    global_stats["avg_processing_time"] = (
                        (global_stats["avg_processing_time"] * (global_stats["successful_requests"] - 1) + processing_time) / 
                        global_stats["successful_requests"]
                    )
                        
                except Exception as e:
                    app.logger.error(f"Error processing request {task.request_id}: {e}", exc_info=True)
                    task.result_future.set_exception(e)
                    global_stats["failed_requests"] += 1
                finally:
                    active_requests.pop(task.request_id, None)
                    
            request_queue.task_done()
            
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            app.logger.error(f"Worker error: {e}", exc_info=True)
            await asyncio.sleep(0.1)

def update_request_stats():
    """Update global request statistics"""
    global_stats["total_requests"] += 1
    global_stats["last_request_time"] = time.time()

# Start more background workers for better concurrency
@app.before_serving
async def startup():
    # Start 8 worker tasks (increased from 3)
    for i in range(8):
        asyncio.create_task(process_request_worker())
    app.logger.info("Started 8 request processing workers")




def extract_query_and_image(data: dict) -> tuple[str, str | None, bool]:
    """
    Extracts user_query and user_image from request data. Returns (query, image_url, is_openai_format).
    """
    user_query = ""
    user_image = None
    is_openai_chat = False

    messages = data.get("messages", [])
    if messages and isinstance(messages, list):
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):  # OpenAI-style with multiple parts
                    for part in content:
                        if part.get("type") == "text":
                            user_query += part.get("text", "").strip() + " "
                        elif part.get("type") == "image_url" and not user_image:
                            user_image = part.get("image_url", {}).get("url", None)
                    user_query = user_query.strip()
                else:  # Old style: plain string content
                    user_query = content.strip()
                is_openai_chat = True
                break

    if not user_query:
        user_query = data.get("query") or data.get("message") or data.get("prompt") or ""

    if not user_image:
        user_image = data.get("image") or data.get("user_image") or data.get("image_url") or None

    return user_query.strip(), user_image, is_openai_chat



@app.route("/search/sse", methods=["POST", "GET"])
async def search_sse(forwarded_data=None):
    if forwarded_data is not None:
        data = forwarded_data
    elif request.method == "GET":
        args = request.args
        stream_flag = args.get("stream", "true").lower() == "true"
        user_query = args.get("query", "").strip()
        user_image = args.get("image") or args.get("image_url") or None
        data = {"query": user_query, "image": user_image}
    else:
        data = await request.get_json(force=True, silent=True) or {}

    user_query, user_image, _ = extract_query_and_image(data)

    request_id = f"sse-{uuid.uuid4().hex[:8]}"
    event_id = f"elixpo-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    update_request_stats()
    app.logger.info(f"SSE request {request_id}: {user_query[:50]}...")

    if len(active_requests) >= 15:
        return Response('data: {"error": "Server overloaded, try again later"}\n\n',
                        content_type="text/event-stream")

    async def event_stream():
        try:
            active_requests[request_id] = {
                "type": "sse",
                "query": user_query[:50],
                "start_time": time.time()
            }

            async with processing_semaphore:
                async for chunk in run_elixposearch_pipeline(user_query, user_image, event_id):
                    lines = chunk.splitlines()
                    event_type = None
                    data_lines = []

                    for line in lines:
                        if line.startswith("event:"):
                            event_type = line.replace("event:", "").strip()
                        elif line.startswith("data:"):
                            data_lines.append(line.replace("data:", "").strip())

                    data_text = "\n".join(data_lines)
                    if data_text:
                        json_data = {
                            "choices": [{"delta": {"content": data_text}}]
                        }
                        yield f"data: {json.dumps(json_data)}\n\n"

                    if event_type == "final":
                        break

                    await asyncio.sleep(0.01)

            yield "data: [DONE]\n\n"

        except Exception as e:
            app.logger.error(f"SSE error for {request_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_requests.pop(request_id, None)
            global_stats["successful_requests"] += 1

    return Response(event_stream(), content_type="text/event-stream")


@app.route('/search', methods=['GET', 'POST'])
@app.route('/search/<path:anything>', methods=['GET', 'POST'])
async def search_json(anything=None):
    request_id = f"json-{uuid.uuid4().hex[:8]}"
    update_request_stats()

    if request.method == "GET":
        args = request.args
        stream_flag = args.get("stream", "false").lower() == "true"
        user_query = args.get("query", "").strip()
        user_image = args.get("image") or args.get("image_url") or None
        data = {"query": user_query, "image": user_image}
    else:
        data = await request.get_json(force=True, silent=True) or {}
        stream_flag = data.get("stream", False)

    user_query, user_image, is_openai_chat = extract_query_and_image(data)

    if stream_flag:
        # Forward to SSE
        sse_data = {
            "messages": [{"role": "user", "content": user_query}] if user_query else [],
            "image": user_image,
            "stream": True
        }

        return await search_sse(forwarded_data=sse_data)

    if not user_query and not user_image:
        return jsonify({"error": "Missing query or image"}), 400

    app.logger.info(f"JSON request {request_id}: {user_query[:50]}...")
    task = RequestTask(request_id, (user_query, user_image), 'json')

    try:
        await asyncio.wait_for(request_queue.put(task), timeout=5.0)
    except asyncio.TimeoutError:
        return jsonify({"error": "Server overloaded, try again later"}), 503

    try:
        async def run_pipeline():
            uq, ui = task.user_query if isinstance(task.user_query, tuple) else (task.user_query, None)
            final_result_content = []
            async for chunk in run_elixposearch_pipeline(uq, ui, event_id=None):
                lines = chunk.splitlines()
                event_type = None
                data_lines = []

                for line in lines:
                    if line.startswith("event:"):
                        event_type = line.replace("event:", "").strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.replace("data:", "").strip())

                data_text = "\n".join(data_lines)
                if data_text and event_type in ["final", "final-part"]:
                    final_result_content.append(data_text)

            return "\n".join(final_result_content).strip() or "No results found"

        final_response = await asyncio.wait_for(run_pipeline(), timeout=180)

    except asyncio.TimeoutError:
        final_response = "Request timed out"
        app.logger.error(f"Request {request_id} timed out")
    except Exception as e:
        final_response = f"Error: {e}"
        app.logger.error(f"Request {request_id} failed: {e}")

    if is_openai_chat:
        return jsonify([{"message": {"role": "assistant", "content": final_response}}])
    else:
        return jsonify({"result": final_response})


# Ultra-fast status endpoint
@app.route("/status", methods=["GET"])
async def status():
    current_time = time.time()
    uptime = current_time - global_stats["start_time"]
    
    return jsonify({
        "status": "healthy",
        "timestamp": current_time,
        "uptime_seconds": round(uptime, 2),
        "queue": {
            "pending": request_queue.qsize(),
            "processing": len(active_requests),
            "capacity": 100,
            "available_slots": max(0, 15 - len(active_requests))
        },
        "stats": {
            "total_requests": global_stats["total_requests"],
            "successful": global_stats["successful_requests"],
            "failed": global_stats["failed_requests"],
            "avg_processing_time": round(global_stats["avg_processing_time"], 2),
            "requests_per_second": round(global_stats["total_requests"] / uptime if uptime > 0 else 0, 2)
        },
        "workers": 8,
        "max_concurrent": 15
    })


@app.route("/transcript", methods=["GET"])
async def transcript():
    now = datetime.utcnow()
    window = transcript_rate_limit["window"]
    limit = transcript_rate_limit["limit"]
    reqs = transcript_rate_limit["requests"]

    # Remove requests outside the window
    while reqs and (now - reqs[0]).total_seconds() > window:
        reqs.popleft()
    if len(reqs) >= limit:
        return jsonify({"error": "Rate limit exceeded. Max 20 requests per minute."}), 429
    reqs.append(now)
    # --- End rate limiting logic ---

    video_url = request.args.get("url") or request.args.get("video_url")
    video_id = request.args.get("id") or request.args.get("video_id")
    if not video_url and not video_id:
        return jsonify({"error": "Missing 'url' or 'id' parameter"}), 400

    if not video_url and video_id:
        video_url = f"https://youtu.be/{video_id}"

    # Fetch transcript (sync function, so run in executor)
    loop = asyncio.get_event_loop()
    transcript_text = await loop.run_in_executor(
        None, lambda: get_youtube_transcript(video_url)
    )

    if not transcript_text:
        return jsonify({"error": "Transcript not available"}), 404

    return jsonify({"transcript": transcript_text})



@app.route("/health", methods=["GET"])
async def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = False
    config.workers = 1
    config.backlog = 1000  
    asyncio.run(hypercorn.asyncio.serve(app, config))