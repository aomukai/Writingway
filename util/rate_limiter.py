import time
import threading
from collections import deque
from typing import Dict, Any, Optional

# Default rate limits for providers
DEFAULT_RATE_LIMITS = {
    "OpenAI": {"min_delay": 1.0, "max_concurrent": 100},  # No practical limit
    "Anthropic": {"min_delay": 1.0, "max_concurrent": 100},  # No practical limit
    "Ollama": {"min_delay": 1.0, "max_concurrent": 1},  # Local inference can only handle one request
    "OpenRouter": {"min_delay": 2.0, "max_concurrent": 100},  # No practical limit
    "TogetherAI": {"min_delay": 2.0, "max_concurrent": 100},  # No practical limit
    "LMStudio": {"min_delay": 1.0, "max_concurrent": 1},  # Local inference can only handle one request
    "Gemini": {"min_delay": 1.0, "max_concurrent": 100},  # No practical limit
    "Custom": {"min_delay": 1.0, "max_concurrent": 100}  # No practical limit
}

class RateLimiter:
    def __init__(self, provider_name: str, min_delay: Optional[float] = None, max_concurrent: Optional[int] = None):
        # Use provided values or defaults for the provider
        defaults = DEFAULT_RATE_LIMITS.get(provider_name, DEFAULT_RATE_LIMITS["Custom"])
        self.min_delay = min_delay if min_delay is not None else defaults["min_delay"]
        self.max_concurrent = max_concurrent if max_concurrent is not None else defaults["max_concurrent"]
        
        self.request_timestamps = deque()
        self.lock = threading.Lock()
        self.active_requests = 0
        self.active_requests_lock = threading.Lock()

    def __enter__(self):
        # Wait for available concurrency slot
        while True:
            with self.active_requests_lock:
                if self.active_requests < self.max_concurrent:
                    self.active_requests += 1
                    break
            time.sleep(0.1)  # Small delay before checking again
        
        with self.lock:
            if self.request_timestamps:
                elapsed = time.monotonic() - self.request_timestamps[-1]
                if elapsed < self.min_delay:
                    time.sleep(self.min_delay - elapsed)
            
            self.request_timestamps.append(time.monotonic())
            if len(self.request_timestamps) > 100: # Keep the deque size manageable
                self.request_timestamps.popleft()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self.active_requests_lock:
            self.active_requests -= 1
