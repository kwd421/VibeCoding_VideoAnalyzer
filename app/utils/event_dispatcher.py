import threading
from typing import Callable, Dict, List, Any

class EventEmitter:
    """[시니어 패턴] 옵저버 패턴을 이용한 이벤트 기반 비동기 통신 시스템"""
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        
    def on(self, event: str, listener: Callable):
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(listener)
            
    def off(self, event: str, listener: Callable):
        with self._lock:
            if event in self._listeners and listener in self._listeners[event]:
                self._listeners[event].remove(listener)
                
    def emit(self, event: str, *args, **kwargs):
        with self._lock:
            listeners = self._listeners.get(event, [])[:]
        for listener in listeners:
            listener(*args, **kwargs)
