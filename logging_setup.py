import logging
import sys


class _ColorFormatter(logging.Formatter):

    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREY   = "\033[38;5;245m"
    CYAN   = "\033[38;5;51m"
    YELLOW = "\033[38;5;220m"
    RED    = "\033[38;5;196m"
    PURPLE = "\033[38;5;135m"

    LEVEL_STYLES = {
        logging.DEBUG:    (GREY,   "ᴅᴇʙᴜɢ  "),
        logging.INFO:     (CYAN,   "ɪɴꜰᴏ   "),
        logging.WARNING:  (YELLOW, "ᴡᴀʀɴ   "),
        logging.ERROR:    (RED,    "ᴇʀʀᴏʀ  "),
        logging.CRITICAL: (RED,    "ᴄʀɪᴛɪᴄ "),
    }

    def format(self, record: logging.LogRecord) -> str:
        color, label = self.LEVEL_STYLES.get(record.levelno, (self.GREY, "?      "))
        ts   = self.formatTime(record, "%H:%M:%S")
        name = record.name.split(".")[-1][:16].ljust(16)
        return (
            f"{self.GREY}{ts}{self.RESET} "
            f"{self.BOLD}{color}{label}{self.RESET} "
            f"{self.PURPLE}{name}{self.RESET}  "
            f"{record.getMessage()}"
        )


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(_ColorFormatter())
    root.addHandler(console)

    file_h = logging.FileHandler("bot.log", encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root.addHandler(file_h)

    for noisy in ("pyrogram", "aiohttp", "aiohttp.access", "aiohttp.server", "motor", "pymongo"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
