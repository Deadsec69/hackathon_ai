import time
from threading import Thread

class TestApplication:
    def __init__(self):
        self.cpu_intensive_task_running = False
        self.cpu_intensive_task_thread = None

    def start(self):
        self.cpu_intensive_task_thread = Thread(target=self.cpu_intensive_task)
        self.cpu_intensive_task_thread.start()

    def cpu_intensive_task(self):
        self.cpu_intensive_task_running = True
        while self.cpu_intensive_task_running:
            # Perform CPU-intensive operations here
            time.sleep(0.1)  # Simulate CPU-intensive work

    def stop(self):
        self.cpu_intensive_task_running = False
        if self.cpu_intensive_task_thread:
            self.cpu_intensive_task_thread.join()

app = TestApplication()
app.start()
# ... (application logic)
app.stop()