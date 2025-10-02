
from collections import deque
from loguru import logger
from getYoutubeDetails import get_youtube_metadata, get_youtube_transcript
from scrape import fetch_full_text
import concurrent 
import os
import re
import asyncio
import random
_deepsearch_store = {}



def preprocess_text(text):
    # Remove URLs, special characters, and clean up
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    text = re.sub(r'[^\w\s.,!?;:]', ' ', text)
    
    # Split into sentences more intelligently
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Filter out short or meaningless sentences
    meaningful_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 20 and len(sentence.split()) > 3:
            # Remove sentences that are mostly navigation/UI elements
            if not any(word in sentence.lower() for word in ['feedback', 'menu', 'navigation', 'click', 'download']):
                meaningful_sentences.append(sentence)
    
    return meaningful_sentences[:15]


async def web_search(query, agent=None):
    from yahooSearch import web_search as yahoo_web_search
    return await yahoo_web_search(query)

async def image_search(query, agent=None, max_images=10):
    from yahooSearch import image_search as yahoo_image_search
    return await yahoo_image_search(query, max_images)

def fetch_url_content_parallel(urls, max_workers=10):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_full_text, url): url for url in urls}
        results = ""
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                text_content = future.result()
                clean_text = str(text_content).encode('unicode_escape').decode('utf-8')
                clean_text = clean_text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
                clean_text = ''.join(c for c in clean_text if c.isprintable())
                results += f"\nURL: {url}\nText Preview: {clean_text.strip()}"
            except Exception as e:
                logger.error(f"Failed fetching {url}: {e}")
                results += f"\nURL: {url}\n Failed to fetch content of this URL"
        logger.info(f"Fetched all URL information in parallel.")
        sentences = preprocess_text(results)

        return results

def fetch_youtube_parallel(urls, mode='metadata', max_workers=10):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        if mode == 'metadata':
            futures = {executor.submit(get_youtube_metadata, url): url for url in urls}
        else:
            futures = {executor.submit(get_youtube_transcript, url): url for url in urls}

        results = {}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as e:
                logger.error(f"YouTube {mode} failed for {url}: {e}")
                results[url] = '[Failed]'
        return results





def storeDeepSearchQuery(query: list, sessionID: str):
    _deepsearch_store[sessionID] = query

def getDeepSearchQuery(sessionID: str):
    return _deepsearch_store.get(sessionID)

def cleanDeepSearchQuery(sessionID: str):
    if sessionID in _deepsearch_store:
        del _deepsearch_store[sessionID]