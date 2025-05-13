from concurrent.futures import ThreadPoolExecutor
import threading

# Maximum number of worker threads in the pool
MAX_WORKERS = 10

# Initialize the thread pool executor
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Lock to protect shared resources
lock = threading.Lock()

def process_request(request):
    """
    Process the incoming request.
    """
    # Acquire the lock to protect shared resources
    with lock:
        # Simulate some CPU-intensive work
        result = cpu_intensive_task(request)
    
    return result

def cpu_intensive_task(data):
    """
    Simulates a CPU-intensive task.
    """
    # Implement your CPU-intensive logic here
    # Avoid infinite loops or excessive computations
    pass

def api_process_endpoint(request):
    """
    API endpoint for processing requests.
    """
    try:
        # Submit the request to the thread pool executor
        future = executor.submit(process_request, request)
        
        # Wait for the result with a timeout
        result = future.result(timeout=60)  # Adjust the timeout as needed
        
        return result
    except Exception as e:
        # Handle exceptions and return an appropriate response
        return {"error": str(e)}