from global_settings.global_settings import GlobalSettings


class ConvertLogger:
    def __init__(self):
        self.logs = {
            'error': [],
            'info': [],
            'warning': [],
        }

    def log(self, log_type, msg):
        if log_type in self.logs:
            self.logs[log_type].append(msg)
            GlobalSettings.logger.debug(f"CONVERTER {log_type.upper()}: {msg}")

    def warning(self, msg):
        self.log('warning', msg)

    def error(self, msg):
        self.log('error', msg)

    def info(self, msg):
        self.log('info', msg)
