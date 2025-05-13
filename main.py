
def simulate_memory_spike():
    global memory_spike_active, allocated_memory
    memory_spike_active = True
    MEMORY_SPIKE_COUNTER.inc()
    
    print(f"[Memory Spike] Starting memory spike simulation")
    
    # Simulate memory spike by allocating memory
    try:
        # Allocate ~700MB of memory in smaller chunks
        total_allocated = 0
        chunk_size = 1 * 1024 * 1024  # 1MB chunks
        for i in range(700):
            allocated_memory.append(bytearray(chunk_size))
            total_allocated += chunk_size
            if i % 50 == 0:  # Print progress every 50MB
                print(f"[Memory Spike] Allocated {total_allocated / (1024 * 1024):.1f} MB")
    except MemoryError as e:
        print(f"[Memory Spike] Memory allocation error: {e}")
    
    print(f"[Memory Spike] Memory allocation complete, holding for 60 seconds")
    
    # Keep the memory allocated for 60 seconds
    time.sleep(60)
    
    # Release memory
    print(f"[Memory Spike] Releasing allocated memory")
    del allocated_memory[:]
    memory_spike_active = False
    print(f"[Memory Spike] Memory spike simulation completed")
