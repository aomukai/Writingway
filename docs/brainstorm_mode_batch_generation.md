# Brainstorm Mode Batch Generation Implementation

## Overview
The batch generation system will handle sending multiple requests to different LLM providers with configurable parameters, while respecting rate limits and handling errors gracefully.

## Core Components

### 1. BrainstormWorker
A new worker class that extends QThread to handle the batch generation process.

#### Responsibilities:
- Manage multiple run groups with different configurations
- Handle rate limiting and delays between requests
- Track progress and emit status updates
- Handle cancellation requests
- Collect and store results from all requests

#### Key Methods:
- `run()`: Main execution loop that processes all run groups
- `process_run_group()`: Process a single run group with multiple runs
- `send_request()`: Send a single request to an LLM with error handling
- `apply_rate_limiting()`: Apply delays between requests based on configuration
- `cancel()`: Handle cancellation requests

### 2. RunGroup
A data structure to represent a group of runs with the same configuration.

#### Attributes:
- `model`: Model configuration (provider, model name, etc.)
- `runs`: Number of runs to execute
- `temperature`: Temperature setting for the model
- `delay`: Delay between requests (in seconds)
- `retries`: Number of retries for failed requests
- `backoff_factor`: Exponential backoff factor for retries

### 3. RequestManager
A component to manage concurrent requests and rate limiting.

#### Responsibilities:
- Track active requests per provider
- Enforce concurrency limits
- Handle 429/5xx errors with exponential backoff
- Queue requests when concurrency limits are reached

#### Key Methods:
- `submit_request()`: Submit a request with rate limiting
- `handle_rate_limit_error()`: Handle 429 errors with backoff
- `handle_server_error()`: Handle 5xx errors with backoff

## Implementation Flow

1. **Initialization**
   - Parse run groups from UI configuration
   - Initialize RequestManager with provider-specific limits
   - Set up progress tracking

2. **Execution Loop**
   - For each run group:
     - For each run in the group:
       - Apply rate limiting delay
       - Send request to LLM
       - Handle errors with retries and backoff
       - Collect successful responses
       - Update progress

3. **Rate Limiting**
   - Apply configured delays between requests
   - Handle 429 errors with exponential backoff
   - Respect provider-specific concurrency limits
   - Queue requests when limits are exceeded

4. **Error Handling**
   - Retry failed requests with exponential backoff
   - Skip to next model after max retries
   - Continue with other run groups if one fails
   - Report errors to UI

5. **Completion**
   - Collect all successful responses
   - Pass results to judge evaluation system
   - Emit completion signal with results

## Integration with Existing System

The batch generation system will integrate with the existing LLM infrastructure by:
- Using the same WWApiAggregator for sending requests
- Reusing existing provider configurations
- Leveraging existing error handling patterns
- Emitting progress updates through Qt signals

## Performance Considerations

- Use threading to avoid blocking the UI
- Implement efficient queuing for rate limiting
- Minimize memory usage by streaming responses when possible
- Handle large numbers of requests efficiently