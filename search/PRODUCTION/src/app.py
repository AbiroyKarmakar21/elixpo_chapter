from quart import Quart, request, jsonify, Response
from quart_cors import cors
import time
import random
import logging
import sys
import uuid
from searchPipeline import run_elixposearch_pipeline, initialize_search_agents
from deepSearchPipeline import run_deep_research_pipeline
import asyncio
import hypercorn.asyncio
import json
import uuid
import multiprocessing as mp
from hypercorn.config import Config
from getYoutubeDetails import get_youtube_transcript
from collections import deque
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', stream=sys.stdout)
request_queue = asyncio.Queue(maxsize=100) 
processing_semaphore = asyncio.Semaphore(15)  
active_requests = {}
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
                    final_result_content = []
                    sources = []
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
                        
                        # Extract sources from data
                        if "[SOURCES]" in data_text and "[/SOURCES]" in data_text:
                            try:
                                import re
                                source_match = re.search(r'\[SOURCES\](.*?)\[\/SOURCES\]', data_text, re.DOTALL)
                                if source_match:
                                    sources = json.loads(source_match.group(1))
                            except:
                                pass
                        
                        if data_text and event_type in ["final", "final-part"]:
                            final_result_content.append(data_text)
                    
                    final_response = "\n".join(final_result_content).strip()
                    if not final_response:
                        final_response = "No results found"
                    
                    # Include sources in response
                    if sources:
                        final_response = f"[SOURCES]{json.dumps(sources)}[/SOURCES]\n\n{final_response}"
                    
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
    global_stats["total_requests"] += 1
    global_stats["last_request_time"] = time.time()


def extract_query_and_image(data: dict) -> tuple[str, str | None, bool]:
    user_query = ""
    user_image = None
    is_openai_chat = False
    image_count = 0

    messages = data.get("messages", [])
    if messages and isinstance(messages, list):
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):  
                    for part in content:
                        if part.get("type") == "text":
                            user_query += part.get("text", "").strip() + " "
                        elif part.get("type") == "image_url" and not user_image:
                            user_image = part.get("image_url", {}).get("url", None)
                    user_query = user_query.strip()
                else: 
                    user_query = content.strip()
                is_openai_chat = True
                break

    if not user_query:
        user_query = data.get("query") or ""
        if user_image:
            image_count += 1

    if not user_image:
        user_image = data.get("image") or None
    
    if image_count > 1:
        return user_query.strip(), "__MULTIPLE_IMAGES__", is_openai_chat

    return user_query.strip(), user_image, is_openai_chat


app = Quart(__name__)
app = cors(app, allow_origin="*")
app.logger.setLevel(logging.INFO)


@app.before_serving
async def startup():
    try:
        await initialize_search_agents()
        app.logger.info("Search agents pre-warmed and ready for cold start")
    except Exception as e:
        app.logger.error(f"Failed to initialize search agents: {e}")
        
    for i in range(8):
        asyncio.create_task(process_request_worker())
    app.logger.info("Started 8 request processing workers")


@app.route("/metadata", methods=["GET"])
def get_metadata():
    if request.method == "GET":
        url = request.args.get("url")
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    metadata = {
        "title": soup.title.string if soup.title else None,
        "description": soup.find("meta", attrs={"name": "description"})["content"]
            if soup.find("meta", attrs={"name": "description"}) else None,
        "og_title": soup.find("meta", property="og:title")["content"]
            if soup.find("meta", property="og:title") else None,
        "og_description": soup.find("meta", property="og:description")["content"]
            if soup.find("meta", property="og:description") else None,
        "og_image": soup.find("meta", property="og:image")["content"]
            if soup.find("meta", property="og:image") else None,
    }

    response = {
        "url": url,
        "metadata": metadata["description"]
    }

    return jsonify(response)



@app.route("/search/sse", methods=["POST", "GET"])
async def search_sse(forwarded_data=None):
    import time

    if forwarded_data is not None:
        data = forwarded_data
    elif request.method == "GET":
        args = request.args
        stream_flag = args.get("stream", "true").lower() == "true"
        user_query = args.get("query", "").strip()
        user_image = args.get("image") or args.get("image_url") or None
        deep_flag = args.get("deep", "false").lower() == "true"
        data = {"query": user_query, "image": user_image, "deep": deep_flag}
    else:
        data = await request.get_json(force=True, silent=True) or {}

    user_query, user_image, _ = extract_query_and_image(data)
    deep_flag = data.get("deep", False)

    # OpenAI-style chunking fields
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created = int(time.time())
    model_name = "elixposearch"

    request_id = f"sse-{uuid.uuid4().hex[:8]}"
    event_id = f"elixpo-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    update_request_stats()
    app.logger.info(f"SSE request {request_id}: {user_query[:50]}... (deep={deep_flag})")

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

            first_chunk = True
            sources_sent = False
            
            async with processing_semaphore:
                # Choose pipeline based on deep_flag
                if deep_flag:
                    pipeline = run_deep_research_pipeline
                else:
                    pipeline = run_elixposearch_pipeline

                async for chunk in pipeline(user_query, user_image, event_id):
                    lines = chunk.splitlines()
                    event_type = None
                    data_lines = []
                    stage = None
                    progress = None
                    finished = None
                    task_num = None

                    for line in lines:
                        if line.startswith("event:"):
                            event_type = line.replace("event:", "").strip()
                        elif line.startswith("stage:"):
                            stage = line.replace("stage:", "").strip()
                        elif line.startswith("progress:"):
                            try:
                                progress = int(line.replace("progress:", "").strip())
                            except Exception:
                                progress = None
                        elif line.startswith("finished:"):
                            finished = line.replace("finished:", "").strip()
                        elif line.startswith("task:"):
                            try:
                                task_num = int(line.replace("task:", "").strip())
                            except Exception:
                                task_num = None
                        elif line.startswith("data:"):
                            data_lines.append(line.replace("data:", "").strip())

                    data_text = "\n".join(data_lines)
                    
                    # Extract and send sources first
                    if "[SOURCES]" in data_text and "[/SOURCES]" in data_text and not sources_sent:
                        try:
                            import re
                            source_match = re.search(r'\[SOURCES\](.*?)\[\/SOURCES\]', data_text, re.DOTALL)
                            if source_match:
                                sources_chunk = {
                                    "id": chat_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model_name,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": f"[SOURCES]{source_match.group(1)}[/SOURCES]"
                                        },
                                        "logprobs": None,
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(sources_chunk)}\n\n"
                                sources_sent = True
                                # Remove sources from data_text
                                data_text = re.sub(r'\[SOURCES\].*?\[\/SOURCES\]', '', data_text, flags=re.DOTALL).strip()
                        except Exception as e:
                            app.logger.error(f"Error processing sources: {e}")
                    
                    # Always include progress and stage metadata
                    if data_text or stage or progress is not None:
                        chunk_obj = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "logprobs": None,
                                "finish_reason": None
                            }]
                        }
                        
                        # Add metadata
                        meta = {}
                        if progress is not None:
                            meta["progress"] = progress
                        if stage is not None:
                            meta["stage"] = stage
                        if task_num is not None:
                            meta["task"] = task_num
                        if finished is not None:
                            meta["finished"] = finished
                        
                        if meta:
                            chunk_obj["choices"][0]["delta"]["elixpo_meta"] = meta

                        if first_chunk:
                            chunk_obj["choices"][0]["delta"]["role"] = "assistant"
                            first_chunk = False
                            if data_text:
                                chunk_obj["choices"][0]["delta"]["content"] = data_text
                            yield f"data: {json.dumps(chunk_obj)}\n\n"
                        else:
                            if data_text:
                                chunk_obj["choices"][0]["delta"]["content"] = data_text
                                yield f"data: {json.dumps(chunk_obj)}\n\n"
                            elif meta:  # Send metadata even without content
                                yield f"data: {json.dumps(chunk_obj)}\n\n"

                    # Use event_type and/or finished to determine when to stop
                    if event_type in ["final", "FINAL_ANSWER"] or (finished and finished.lower() == "yes"):
                        finish_obj = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": ""},
                                "logprobs": None,
                                "finish_reason": "stop",
                                "stop_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(finish_obj)}\n\n"
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
        deep_flag = args.get("deep", "false").lower() == "true"
        data = {"query": user_query, "image": user_image, "deep": deep_flag}
    else:
        data = await request.get_json(force=True, silent=True) or {}
        stream_flag = data.get("stream", False)
        deep_flag = data.get("deep", False)

    user_query, user_image, _ = extract_query_and_image(data)

    if stream_flag or deep_flag:
        # Forward to SSE, always stream for deep search
        sse_data = {
            "messages": [{"role": "user", "content": user_query}] if user_query else [],
            "image": user_image,
            "stream": True,
            "deep": deep_flag
        }
        return await search_sse(forwarded_data=sse_data)

    if user_image == "__MULTIPLE_IMAGES__":
        return jsonify({"error": "Only one image can be processed per request. Please submit a single image."}), 400

    if not user_query and not user_image:
        return jsonify({"error": "Missing query or image"}), 400

    app.logger.info(f"JSON request {request_id}: {user_query[:50]}... (deep={deep_flag})")
    task = RequestTask(request_id, (user_query, user_image), 'json')

    try:
        await asyncio.wait_for(request_queue.put(task), timeout=5.0)
    except asyncio.TimeoutError:
        return jsonify({"error": "Server overloaded, try again later"}), 503

    try:
        # Wait for the worker to process the task
        final_response = await asyncio.wait_for(task.result_future, timeout=180)
    except asyncio.TimeoutError:
        final_response = "Request timed out"
        app.logger.error(f"Request {request_id} timed out")
    except Exception as e:
        final_response = f"Error: {e}"
        app.logger.error(f"Request {request_id} failed: {e}")

    # Always return OpenAI-style response
    return jsonify({
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": final_response
                }
            }
        ]
    })

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


@app.route("/test", methods=["GET"])
async def testResponse():
    return jsonify({
        "choices" : [
            {
                "message" : {
                    "role" : "assistant",
                    "content" : "as of Tuesday, September 9, 2025, here's the latest news from Nepal:\n\n**Major Political Unrest and Protests:**\n\n*   **Prime Minister Resigns Amidst Widespread Protests:** Prime Minister K. P. Sharma Oli resigned from his position on Tuesday, September 9, 2025. This resignation followed a period of intense mass protests and significant unrest across the country.\n*   **Violence and Arson:** The protests escalated to a point where protesters entered the parliament building and set it on fire. There are also reports of government ministers being attacked and their homes being targeted.\n*   **Gen Z-Led Movement:** A significant driving force behind the recent protests appears to be Nepal's Generation Z, who are expressing deep anger and dissatisfaction, demanding not only the Prime Minister's resignation but also broader systemic changes. Their sentiment is captured in slogans like \"Topple this government.\"\n*   **Airport Closure:** As a consequence of the unrest, the airport in Nepal was shut down, indicating the severity of the situation and its impact on daily life and national operations.\n*   **Social Media Restrictions:** In response to the ongoing protests and to manage information flow, there were reports of a social media ban being implemented.\n\n**Contextual Information:**\n\nThe news indicates a period of significant political instability in Nepal. The mass protests, seemingly fueled by a younger generation's demand for change, have led to a change in leadership and widespread disruption. The actions taken, such as setting fire to parliament and closing the airport, highlight the intensity of the public's dissatisfaction. The government's response, including a potential social media ban, suggests efforts to control the narrative and maintain order amidst the chaos.\n\nIt's important to note that this is a developing situation, and further updates would be necessary to understand the long-term implications of these events on Nepal's political landscape.\n\n---\n**Sources:**\n1. [https://english.nepalnews.com/](https://english.nepalnews.com/)\n2. [https://www.aljazeera.com/features/2025/9/9/we-want-mass-resignations-nepals-gen-z-anger-explodes-after-19-killed](https://www.aljazeera.com/features/2025/9/9/we-want-mass-resignations-nepals-gen-z-anger-explodes-after-19-killed)\n3. [https://www.aljazeera.com/news/liveblog/2025/9/9/nepal-protests-live-nepali-congress-office-top-leaders-homes-set-on-fire](https://www.aljazeera.com/news/liveblog/2025/9/9/nepal-protests-live-nepali-congress-office-top-leaders-homes-set-on-fire)\n4. [https://www.cnn.com/2025/09/09/asia/nepal-protests-social-media-ban-explainer-intl-hnk](https://www.cnn.com/2025/09/09/asia/nepal-protests-social-media-ban-explainer-intl-hnk)\n5. [https://www.firstpost.com/explainers/photos-videos-nepal-protests-gen-z-13932219.html](https://www.firstpost.com/explainers/photos-videos-nepal-protests-gen-z-13932219.html)"
                }
            }
        ]
    })


@app.route("/transcript", methods=["GET"])
async def transcript():
    now = datetime.utcnow()
    window = transcript_rate_limit["window"]
    limit = transcript_rate_limit["limit"]
    reqs = transcript_rate_limit["requests"]

    while reqs and (now - reqs[0]).total_seconds() > window:
        reqs.popleft()
    if len(reqs) >= limit:
        return jsonify({"error": "Rate limit exceeded. Max 20 requests per minute."}), 429
    reqs.append(now)

    video_url = request.args.get("url") or request.args.get("video_url")
    video_id = request.args.get("id") or request.args.get("video_id")
    if not video_url and not video_id:
        return jsonify({"error": "Missing 'url' or 'id' parameter"}), 400

    if not video_url and video_id:
        video_url = f"https://youtu.be/{video_id}"

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

@app.route("/embedding/health", methods=["GET"])
async def embedding_health():
    """Check embedding server connectivity and status"""
    try:
        from embeddingClient import get_embedding_client
        client = get_embedding_client()
        active_ops = client.get_active_operations_count()
        
        return jsonify({
            "status": "ok",
            "embedding_server": "connected", 
            "active_operations": active_ops,
            "ipc_enabled": True
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "embedding_server": "disconnected",
            "error": str(e),
            "ipc_enabled": False
        }), 503

@app.route("/embedding/stats", methods=["GET"])
async def embedding_stats():
    """Get detailed embedding server statistics"""
    try:
        from embeddingClient import get_embedding_client
        from textEmbedModel import is_using_ipc_embedding
        
        client = get_embedding_client()
        active_ops = client.get_active_operations_count()
        
        return jsonify({
            "status": "ok",
            "ipc_mode": is_using_ipc_embedding(),
            "server_address": "localhost:5002",
            "active_operations": active_ops,
            "total_requests": global_stats["total_requests"],
            "successful_requests": global_stats["successful_requests"], 
            "failed_requests": global_stats["failed_requests"],
            "uptime": time.time() - global_stats["start_time"]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    import os
    
    # Get port from environment variable, default to 5000
    port = int(os.getenv("PORT", 5000))
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.use_reloader = False
    config.workers = 15
    config.backlog = 1000
    
    print(f"Starting Elixpo Search API on port {port}")
    asyncio.run(hypercorn.asyncio.serve(app, config))