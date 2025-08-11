# Brainstorm Mode Rate Limiting and Throttling Mechanism

## Overview
The rate limiting and throttling mechanism ensures that requests to LLM providers are sent at appropriate intervals to avoid hitting rate limits and to respect provider constraints.

## Core Components

### 1. RateLimiter
A component that manages rate limiting for each provider.

#### Responsibilities:
- Track request timestamps for each provider
- Enforce configured delays between requests
- Handle provider-specific rate limits
- Implement exponential backoff for errors

#### Key Methods:
- `wait_if_needed()`: Wait before sending a request if needed
- `record_request()`: Record a request timestamp
- `handle_rate_limit_error()`: Handle 429 errors with backoff
- `handle_server_error()`: Handle 5xx errors with backoff

### 2. ProviderLimits
Configuration for rate limits per provider.

#### Attributes:
- `min_delay`: Minimum delay between requests (in seconds)
- `max_concurrent`: Maximum concurrent requests
- `burst_limit`: Maximum requests in a burst period
- `burst_period`: Time period for burst limit (in seconds)

### 3. BackoffStrategy
Configuration for exponential backoff on errors.

#### Attributes:
- `initial_delay`: Initial delay after first error (in seconds)
- `multiplier`: Multiplier for each subsequent retry
- `max_delay`: Maximum delay between retries (in seconds)
- `max_retries`: Maximum number of retries

## Implementation Details

### 1. Per-Provider Rate Limiting
Each provider will have its own RateLimiter instance with provider-specific limits:
- OpenAI: 1 request per second, 10 concurrent
- Anthropic: 1 request per second, 5 concurrent
- Ollama: 1 request at a time (no concurrent)
- OpenRouter: Provider-specific limits
- TogetherAI: Provider-specific limits

### 2. Configurable Delays
Users can configure delays per run group:
- Minimum delay between requests for that group
- Override provider defaults if needed

### 3. Exponential Backoff
For 429 (rate limit) and 5xx (server) errors:
- Start with initial delay
- Multiply delay by backoff factor for each retry
- Cap delay at maximum value
- Stop after maximum retries

### 4. Concurrency Control
- Track active requests per provider
- Queue requests when concurrency limits are reached
- Release concurrency slots when requests complete

## Error Handling

### 1. Rate Limit Errors (429)
- Parse retry-after header if available
- Apply exponential backoff if no header
- Skip to next model after max retries

### 2. Server Errors (5xx)
- Apply exponential backoff
- Continue with other requests
- Skip to next model after max retries

### 3. Network Errors
- Apply exponential backoff
- Continue with other requests
- Skip to next model after max retries

## Integration Points

- Integrated with the batch generation system
- Uses provider configurations from settings
- Reports rate limit status to UI
- Handles errors gracefully

## Performance Considerations

- Minimize sleep time when possible
- Use efficient data structures for tracking requests
- Avoid blocking UI thread during waits
- Handle large numbers of queued requests efficiently