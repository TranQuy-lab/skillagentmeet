"""Worker threads for asynchronous networking in PyQt5 with high stability and graceful shutdown."""

import time
from typing import Callable, Any
from PyQt5.QtCore import QThread, pyqtSignal
from agentmeet.api_client import AgentMeetClient


class GenericTaskWorker(QThread):
    """Worker thực thi các tác vụ mạng bất đồng bộ an toàn."""

    sig_success = pyqtSignal(object)
    sig_error = pyqtSignal(str)
    sig_finished = pyqtSignal()

    def __init__(self, task_fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.task_fn = task_fn
        self.args = args
        self.kwargs = kwargs
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True

    def run(self):
        try:
            if not self._is_aborted:
                res = self.task_fn(*self.args, **self.kwargs)
                if not self._is_aborted:
                    self.sig_success.emit(res)
        except Exception as e:
            if not self._is_aborted:
                self.sig_error.emit(str(e))
        finally:
            self.sig_finished.emit()


class PollWorker(QThread):
    """
    Worker chạy ngầm định kỳ gọi API read_new_messages với cơ chế chống crash,
    giảm tải lỗi mạng (backoff), và tắt luồng an toàn.
    """

    sig_new_messages = pyqtSignal(list)
    sig_error = pyqtSignal(str)

    def __init__(self, client: AgentMeetClient, agent_token: str, interval: float = 2.0):
        super().__init__()
        self.client = client
        self.agent_token = agent_token
        self.interval = max(0.5, float(interval))
        self._running = True
        self._paused = False
        self._consecutive_errors = 0

    def update_token(self, token: str):
        self.agent_token = token
        self._consecutive_errors = 0

    def set_interval(self, seconds: float):
        self.interval = max(0.5, float(seconds))

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
        self._consecutive_errors = 0

    def stop(self):
        self._running = False
        self.quit()
        if not self.wait(1500):
            self.terminate()

    def run(self):
        while self._running:
            if not self._paused and self.agent_token and self._running:
                try:
                    msgs = self.client.read_new_messages(self.agent_token)
                    if msgs and self._running:
                        self.sig_new_messages.emit(msgs)
                    self._consecutive_errors = 0
                except Exception as e:
                    self._consecutive_errors += 1
                    # Chỉ phát tín hiệu lỗi ở lần đầu hoặc mỗi 5 lần liên tiếp để tránh spam UI
                    if self._consecutive_errors == 1 or self._consecutive_errors % 5 == 0:
                        if self._running:
                            self.sig_error.emit(str(e))
                    # Nghỉ thêm 2s nếu bị lỗi mạng liên tiếp
                    time.sleep(1.0)

            # Chia nhỏ khoảng sleep để phản hồi lệnh stop() ngay lập tức
            elapsed = 0.0
            slice_sec = 0.2
            while elapsed < self.interval and self._running:
                time.sleep(slice_sec)
                elapsed += slice_sec
