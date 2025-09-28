import dotenv from 'dotenv'
dotenv.config();

const POLLINATIONS_TOKEN = process.env.polli_token;
async function generateImageWorker(request) {
  const { prompt, width, height, model, seed, imageMode, uploadedUrl, privateMode } = request;
  
  let generateUrl;
  
  if (imageMode && uploadedUrl) {
    if (model === "kontext") {
      generateUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?model=${model}&image=[${uploadedUrl}]&nologo=true&token=${POLLINATIONS_TOKEN}`;
    } else {
      throw new Error("Image mode only supports kontext model");
    }
  } else {
    generateUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=${width}&height=${height}&model=${model}&nologo=true&referrer=elixpoart&token=${POLLINATIONS_TOKEN}&seed=${seed}`;
  }

  if (privateMode) {
    generateUrl += "&private=true";
  }

  // Implement retry logic with fallback
  const maxRetries = 3;
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Attempt ${attempt} for request ${request.id}`);
      
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000); // 60s timeout
      
      const response = await fetch(generateUrl, { 
        signal: controller.signal,
        headers: {
          'User-Agent': 'ElixpoArt/1.0'
        }
      });
      
      clearTimeout(timeout);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.blob();
      
    } catch (error) {
      lastError = error;
      console.log(`Attempt ${attempt} failed for request ${request.id}:`, error.message);
      
      // If gptimage or kontext fails and not in imageMode, fallback to flux
      if ((model === 'gptimage' || model === 'kontext') && !imageMode && attempt === 2) {
        generateUrl = generateUrl.replace(`model=${model}`, 'model=flux');
        console.log(`Falling back to flux model for request ${request.id}`);
      }
      
      if (attempt < maxRetries) {
        // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
      }
    }
  }
  
  throw lastError || new Error('Image generation failed after all retries');
}

export default generateImageWorker;