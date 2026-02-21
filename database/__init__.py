from .mongodb import Database


class _DbHolder:

    def __init__(self):
        self._instance = None

    def set(self, instance):
        self._instance = instance

    def get(self):
        if self._instance is None:
            raise RuntimeError("Database not initialised yet.")
        return self._instance

    def __getattr__(self, name):
        return getattr(self.get(), name)


db_instance = _DbHolder()
db = db_instance

__all__ = ["Database", "db_instance", "db"]
