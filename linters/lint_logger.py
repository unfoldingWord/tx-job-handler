from global_settings.global_settings import GlobalSettings


class LintLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)
        GlobalSettings.logger.debug(f"LINT ISSUE: {msg}")
