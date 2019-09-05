from app_settings.app_settings import AppSettings


class LintLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)
        AppSettings.logger.debug(f"LINT ISSUE: {msg}")
