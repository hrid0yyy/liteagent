import threading

from .read_tracker import ReadTracker


class AppContainer:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._read_tracker = ReadTracker()

    @classmethod
    def get_instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def read_tracker(self) -> ReadTracker:
        return self._read_tracker


def get_container() -> AppContainer:
    return AppContainer.get_instance()
