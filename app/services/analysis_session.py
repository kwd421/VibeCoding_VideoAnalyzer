import threading


class AnalysisSession:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()

    @property
    def stop_event(self):
        return self._stop_event

    @property
    def thread(self):
        return self._thread

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def request_stop(self):
        self._stop_event.set()

    def request_stop_and_join(self, timeout=None):
        self.request_stop()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        return not self.is_running()

    def reset_stop_event(self):
        self._stop_event = threading.Event()
        return self._stop_event

    def start(self, target, args=(), kwargs=None, daemon=True, name=None):
        kwargs = kwargs or {}
        self._thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon, name=name)
        self._thread.start()
        return self._thread

    def clear_if_finished(self):
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
