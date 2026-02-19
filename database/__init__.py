from .mongodb import Database


class _DbHolder:
    """
    Singleton holder for the Database instance created at startup.

    All plugin handlers do:
        from database import db
        result = await db.get_stats()

    main.py calls db_instance.set(database) once on startup, then every
    subsequent call to db.<method> delegates to the real Database object.
    """

    def __init__(self):
        self._instance: "Database | None" = None

    def set(self, instance: "Database"):
        self._instance = instance

    def get(self) -> "Database":
        if self._instance is None:
            raise RuntimeError(
                "Database not initialised yet. "
                "Call db_instance.set() in main.py before using db."
            )
        return self._instance

    # Transparent proxy: db.get_stats()  ⟹  db._instance.get_stats()
    def __getattr__(self, name: str):
        return getattr(self.get(), name)


# Single instance used across the whole app
db_instance = _DbHolder()

# Short alias — imported by all handlers as `from database import db`
db = db_instance

__all__ = ["Database", "db_instance", "db"]
