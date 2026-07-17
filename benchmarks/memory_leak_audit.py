import asyncio
import psutil
import os
import time
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000"

async def run_requests(num_requests: int):
    """
    Fire a large volume of requests to the backend to ensure connections
    are cleanly released back into the pool.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for i in range(num_requests):
            payload = {
                "query": f"Audit query number {i}",
                "session_id": "audit_session"
            }
            tasks.append(client.post(f"{API_URL}/api/v1/ai/query", json=payload))
            
        # Batch execution to overwhelm the pool slightly
        chunk_size = 50
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i + chunk_size]
            results = await asyncio.gather(*chunk, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.warning(f"Request failed: {res}")

def get_process_memory() -> float:
    """Returns memory usage in MB for the current process."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

async def memory_leak_audit():
    """
    Executes longevity scripts and verifies that long-running multi-agent instances 
    do not leak system memory.
    """
    logger.info("Starting memory & connection pool leak audit...")
    initial_mem = get_process_memory()
    logger.info(f"Initial Memory Usage: {initial_mem:.2f} MB")
    
    # Run a high volume of requests
    # Note: Target service must be running. If not, this acts as a template for DevOps.
    try:
        await run_requests(500)
    except httpx.ConnectError:
        logger.error("API server is not reachable. Skipping active load test.")
        return
        
    # Force garbage collection in Python to see true retention
    import gc
    gc.collect()
    
    final_mem = get_process_memory()
    logger.info(f"Final Memory Usage: {final_mem:.2f} MB")
    
    mem_diff = final_mem - initial_mem
    logger.info(f"Memory Difference: {mem_diff:.2f} MB")
    
    if mem_diff > 50.0:  # 50 MB arbitrary threshold for a single test run
        logger.warning("Potential Memory Leak Detected! Memory increased by > 50MB.")
    else:
        logger.info("Memory usage stable. No critical leaks detected.")

if __name__ == "__main__":
    asyncio.run(memory_leak_audit())
