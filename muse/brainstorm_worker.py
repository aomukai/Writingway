import time
import threading
import random
from dataclasses import dataclass
from typing import List, Dict, Any

from PyQt5.QtCore import QThread, pyqtSignal

from settings.llm_api_aggregator import WWApiAggregator
from util.rate_limiter import RateLimiter

@dataclass
class RunGroup:
    provider: str
    model: str
    runs: int = 1
    temperature: float = 0.7
    delay: float = 1.0
    retries: int = 3
    backoff_factor: float = 2.0
    max_concurrent: int = 5
    max_tokens: int = 1024

class BrainstormWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, run_groups: List[RunGroup], prompt: str, parent=None):
        super().__init__(parent)
        self.run_groups = run_groups
        self.prompt = prompt
        self.is_cancelled = False
        self.results = []
        self.rate_limiters = {}

    def run(self):
        total_runs = sum(group.runs for group in self.run_groups)
        
        # Initialize rate limiters for all providers
        for group in self.run_groups:
            if group.provider not in self.rate_limiters:
                self.rate_limiters[group.provider] = RateLimiter(group.provider, min_delay=group.delay, max_concurrent=group.max_concurrent)

        # Process run groups concurrently using threads
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Create a thread pool with a reasonable number of threads
        max_workers = min(len(self.run_groups), 10)  # Limit to 10 threads max
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks for each run group
            future_to_group = {}
            group_run_counts = {}  # Track run counts per group
            
            for group_idx, group in enumerate(self.run_groups):
                group_run_counts[group_idx] = 0
                for run_idx in range(group.runs):
                    future = executor.submit(self._process_single_run, group, group_idx, run_idx, total_runs, group_run_counts)
                    future_to_group[future] = (group_idx, run_idx)
            
            # Process completed tasks
            completed_runs = 0
            for future in as_completed(future_to_group):
                if self.is_cancelled:
                    break
                    
                group_idx, run_idx = future_to_group[future]
                try:
                    result = future.result()
                    if result:
                        self.results.append(result)
                        completed_runs += 1
                except Exception as e:
                    completed_runs += 1
                    # Error already emitted by _process_single_run
                    
        self.progress_updated.emit(100, "Finished all runs.")
        self.finished.emit(self.results)
        
    def _process_single_run(self, group, group_idx, run_idx, total_runs, group_run_counts):
        """Process a single run within a group."""
        if self.is_cancelled:
            return None
            
        # Update run count for this group
        with threading.Lock():
            group_run_counts[group_idx] += 1
            completed_runs = sum(group_run_counts.values())
            
        self.progress_updated.emit(int((completed_runs / total_runs) * 100), f"Starting run {run_idx+1}/{group.runs} for {group.provider} - {group.model}")

        # Exponential backoff implementation
        retry_count = 0
        while retry_count <= group.retries:
            try:
                with self.rate_limiters[group.provider]:
                    overrides = {
                        "provider": group.provider,
                        "model": group.model,
                        "temperature": group.temperature,
                        "max_tokens": group.max_tokens,
                    }
                    response = WWApiAggregator.send_prompt_to_llm(self.prompt, overrides=overrides)
                    return {
                        "provider": group.provider,
                        "model": group.model,
                        "response": response
                    }
            except Exception as e:
                retry_count += 1
                if retry_count > group.retries:
                    self.error.emit(f"Error during run {run_idx+1} for {group.provider} - {group.model}: {e}")
                    return None
                
                # Check if it's a rate limit or server error (429/5xx)
                error_str = str(e).lower()
                if any(code in error_str for code in ["429", "500", "502", "503", "504"]):
                    # Calculate backoff delay
                    delay = group.delay * (group.backoff_factor ** (retry_count - 1))
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter
                    
                    self.progress_updated.emit(int((completed_runs / total_runs) * 100), f"Rate limited. Retrying in {total_delay:.1f} seconds...")
                    time.sleep(total_delay)
                else:
                    # Non-retryable error
                    self.error.emit(f"Error during run {run_idx+1} for {group.provider} - {group.model}: {e}")
                    return None
                    
        return None

    def cancel(self):
        self.is_cancelled = True
        
    def evaluate_results(self, results: List[Dict[str, Any]], judge_provider: str, judge_model: str, judge_prompt: str) -> str:
        """
        Evaluate the brainstorming results using a judge model.
        
        Args:
            results: List of results from the brainstorming process
            judge_provider: Provider name for the judge model
            judge_model: Model name for the judge model
            judge_prompt: Prompt to use for the judge
            
        Returns:
            Evaluated and ranked results as a string
        """
        # Format the results for the judge
        formatted_results = ""
        for i, result in enumerate(results, 1):
            formatted_results += f"<response {i}>\n{result['response']}\n</response {i}>\n\n"
        
        # Create the full prompt for the judge
        full_prompt = f"{judge_prompt}\n\n{formatted_results}"
        
        # Send the prompt to the judge model
        overrides = {
            "provider": judge_provider,
            "model": judge_model,
        }
        
        # Exponential backoff for judge evaluation
        retry_count = 0
        max_retries = 3
        backoff_factor = 2.0
        delay = 1.0
        
        while retry_count <= max_retries:
            try:
                response = WWApiAggregator.send_prompt_to_llm(full_prompt, overrides=overrides)
                return response
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    return f"Error during evaluation: {e}"
                
                # Check if it's a rate limit or server error (429/5xx)
                error_str = str(e).lower()
                if any(code in error_str for code in ["429", "500", "502", "503", "504"]):
                    # Calculate backoff delay
                    backoff_delay = delay * (backoff_factor ** (retry_count - 1))
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * backoff_delay)
                    total_delay = backoff_delay + jitter
                    
                    time.sleep(total_delay)
                else:
                    # Non-retryable error
                    return f"Error during evaluation: {e}"
        
        # This should never be reached, but just in case
        return "Error: Evaluation failed after all retries."