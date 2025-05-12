import resource

def log_memory_usage():
    mem_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f'Current memory usage: {mem_usage} KB')

# Call log_memory_usage() at strategic points in your code
# For example, before and after processing a request