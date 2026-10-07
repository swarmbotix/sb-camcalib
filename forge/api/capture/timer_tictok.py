import time

class TimerTicTok:
    def __init__(self, window_seconds=1.0):
        self.prev = time.perf_counter()
        self.dt = 0.0
        self.window_seconds = window_seconds
        self.timestamps = []

    def update(self):
        now = time.perf_counter()
        self.dt = now - self.prev
        self.prev = now

        self.timestamps.append(now)
        self.timestamps = [t for t in self.timestamps if (now - t) <= self.window_seconds]

    def pprint(self):
        num_updates = len(self.timestamps)
        if num_updates > 1:
            total_time = self.timestamps[-1] - self.timestamps[0]
            average_freq = (num_updates - 1) / total_time if total_time > 0 else 0.0
        else:
            average_freq = 0.0

        print(f"dt = {self.dt:.2f} sec, freq = {1.0 / self.dt:.2f} Hz, avg freq = {average_freq:.2f} Hz")
