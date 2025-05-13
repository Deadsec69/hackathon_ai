class TestApplication:
    def __init__(self):
        self.available = False

    def check_availability(self):
        # Simulate a check that might be causing high CPU usage
        # Original code might have had an infinite loop or inefficient logic
        # Here, we replace it with a more efficient check
        import time
        time.sleep(0.1)  # Simulate a delay in checking availability
        self.available = True

    def run(self):
        while not self.available:
            self.check_availability()
        print("Test application is now available")

# Create an instance of the application and run it
app = TestApplication()
app.run()