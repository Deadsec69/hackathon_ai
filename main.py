
# CPU intensive task for a single thread
def cpu_intensive_task():
    print(f"[CPU Task] Starting CPU-intensive graph algorithm task")
    iteration = 0
    while cpu_spike_active:
        iteration += 1
        # Generate a new random graph for each iteration
        graph_size = 10  # Reduced graph size to 10 nodes to reduce CPU load
        graph = generate_large_graph(graph_size)
        
        # Pick random start and end nodes
        start_node = random.randint(0, graph_size-1)
        end_node = random.randint(0, graph_size-1)
        while end_node == start_node:
            end_node = random.randint(0, graph_size-1)
        
        print(f"[CPU Task] Iteration {iteration}: Running brute force shortest path algorithm on graph with {graph_size} nodes from node {start_node} to {end_node}")
        
        # Find shortest path using brute force (CPU intensive)
        start_time = time.time()
        path, distance = brute_force_shortest_path(graph, start_node, end_node, max_depth=5)  # Limit max_depth to 5 to reduce CPU load
        elapsed = time.time() - start_time
        
        if path:
            print(f"[CPU Task] Found path with {len(path)} nodes and distance {distance} in {elapsed:.2f} seconds")
        else:
            print(f"[CPU Task] No path found after {elapsed:.2f} seconds")
        
        # Introduce a delay between iterations to reduce CPU load
        time.sleep(0.5)

# CPU spike simulation
def simulate_cpu_spike():
    global cpu_spike_active, cpu_threads
    cpu_spike_active = True
    CPU_SPIKE_COUNTER.inc()
    
    # Create multiple threads to maximize CPU usage
    # Use as many threads as there are CPU cores
    num_cores = min(multiprocessing.cpu_count(), 4)  # Limit the number of threads to 4 to reduce CPU load
    cpu_threads = []
    
    print(f"[CPU Spike] Starting CPU spike simulation with graph-based algorithm")
    print(f"[CPU Spike] Creating {num_cores} threads to maximize CPU usage")
    
    for i in range(num_cores):
        thread = threading.Thread(target=cpu_intensive_task, name=f"cpu-task-{i}")
        thread.daemon = True
        thread.start()
        cpu_threads.append(thread)
    
    print(f"[CPU Spike] All threads started, will run for 30 seconds")  # Reduced simulation duration to 30 seconds
    
    # Run for 30 seconds
    time.sleep(30)
    
    # Stop the CPU spike
    print(f"[CPU Spike] Stopping CPU spike simulation")
    cpu_spike_active = False
    
    # Wait for all threads to finish
    for thread in cpu_threads:
        thread.join(timeout=1)
    
    cpu_threads = []
    print(f"[CPU Spike] CPU spike simulation completed")
