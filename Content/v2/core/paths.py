import os
import sys

PRODUCT_NAME = "MiMo Auto"
STATE_FILE = "install_state.json"
TRANSACTION_FILE = "install_transaction.json"
PORTABLE_FLAG = "portable.flag"
CONFIG_DIR = "config"
LOG_DIR = "logs"
DIAG_DIR = "diagnostics"
BACKUP_DIR = "backups"


def get_install_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)))


def get_log_dir(install_dir=None, portable=False):
    if portable:
        return os.path.join(install_dir or get_install_dir(), LOG_DIR)
    program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    return os.path.join(program_data, "MiMo", LOG_DIR)


def get_config_dir(install_dir=None):
    return os.path.join(install_dir or get_install_dir(), CONFIG_DIR)


def get_state_path(install_dir=None):
    return os.path.join(install_dir or get_install_dir(), STATE_FILE)


def get_transaction_path(install_dir=None):
    return os.path.join(install_dir or get_install_dir(), TRANSACTION_FILE)


def get_backup_dir(install_dir=None):
    return os.path.join(install_dir or get_install_dir(), BACKUP_DIR)


def get_diag_dir(install_dir=None):
    return os.path.join(install_dir or get_install_dir(), DIAG_DIR)


def is_portable(install_dir=None):
    d = install_dir or get_install_dir()
    return os.path.exists(os.path.join(d, PORTABLE_FLAG))


def ensure_dirs(install_dir=None, portable=False):
    dirs = [
        get_log_dir(install_dir, portable),
        get_config_dir(install_dir),
        get_backup_dir(install_dir),
        get_diag_dir(install_dir),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
