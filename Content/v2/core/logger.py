import json
import os
import uuid
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import logging

MAX_LOG_SIZE = 10 * 1024 * 1024
MAX_LOG_FILES = 5


class JSONFormatter(logging.Formatter):
    def __init__(self, component, version):
        super().__init__()
        self.component = component
        self.version = version

    def format(self, record):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": getattr(record, "session_id", "unknown"),
            "component": self.component,
            "level": record.levelname,
            "version": self.version,
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }
        for key in ["dependency", "version_found", "error", "path",
                     "duration_ms", "attempt", "repair_count", "step",
                     "status", "port", "gpu", "disk_free_gb"]:
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, ensure_ascii=False)


class SessionFilter(logging.Filter):
    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id

    def filter(self, record):
        record.session_id = self.session_id
        return True


class MiMoLogger:
    def __init__(self, component, log_dir, version="2.0.0"):
        self.component = component
        self.session_id = uuid.uuid4().hex[:8]
        self.version = version
        self.log_dir = log_dir
        self.logger = logging.getLogger(f"mimo.{component}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.logger.addFilter(SessionFilter(self.session_id))

        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{component}.jsonl")

        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_LOG_SIZE,
            backupCount=MAX_LOG_FILES, encoding="utf-8"
        )
        file_handler.setFormatter(JSONFormatter(component, version))
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            f"[%(asctime)s] [{component}] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S"
        ))
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)

    def _log(self, level, msg, event=None, **kwargs):
        extra = {"event": event or msg.lower().replace(" ", "_")}
        extra.update(kwargs)
        self.logger.log(level, msg, extra=extra)

    def info(self, msg, event=None, **kwargs):
        self._log(logging.INFO, msg, event, **kwargs)

    def warn(self, msg, event=None, **kwargs):
        self._log(logging.WARNING, msg, event, **kwargs)

    def error(self, msg, event=None, **kwargs):
        self._log(logging.ERROR, msg, event, **kwargs)

    def debug(self, msg, event=None, **kwargs):
        self._log(logging.DEBUG, msg, event, **kwargs)

    def dependency_detected(self, name, version):
        self.info(f"{name} detected: {version}", event="dependency_detected",
                  dependency=name, version_found=version)

    def dependency_missing(self, name):
        self.warn(f"{name} not found", event="dependency_missing", dependency=name)

    def dependency_installed(self, name, version=""):
        self.info(f"{name} installed: {version}", event="dependency_installed",
                  dependency=name, version_found=version)

    def step_start(self, step):
        self.info(f"Starting: {step}", event="step_start", step=step)

    def step_complete(self, step, duration_ms=0):
        self.info(f"Completed: {step}", event="step_complete",
                  step=step, duration_ms=duration_ms)

    def step_failed(self, step, error=""):
        self.error(f"Failed: {step} — {error}", event="step_failed",
                   step=step, error=error)

    def repair_start(self, issues):
        self.info(f"Repair started: {len(issues)} issue(s)",
                  event="repair_start", repair_count=len(issues))

    def repair_complete(self, repaired):
        self.info(f"Repair complete: {repaired}",
                  event="repair_complete", repair_count=len(repaired))

    def repair_limit_reached(self, count, max_count):
        self.error(f"Repair limit reached: {count}/{max_count}",
                   event="repair_limit_reached",
                   repair_count=count)

    def health_check_result(self, healthy, issues=None):
        if healthy:
            self.info("Health check: healthy", event="health_check_healthy")
        else:
            self.warn(f"Health check: {len(issues or [])} issue(s)",
                      event="health_check_issues", repair_count=len(issues or []))

    def install_start(self):
        self.info("Installation started", event="install_start")

    def install_complete(self, duration_ms=0):
        self.info(f"Installation complete", event="install_complete",
                  duration_ms=duration_ms)

    def install_failed(self, reason=""):
        self.error(f"Installation failed: {reason}",
                   event="install_failed", error=reason)

    def launch(self, port=0):
        self.info(f"MiMo launched on port {port}",
                  event="launch", port=port)

    def get_log_path(self):
        return os.path.join(self.log_dir, f"{self.component}.jsonl")
