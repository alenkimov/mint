from pathlib import Path

from twitter.utils import copy_file

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent

# Log
LOG_DIR = BASE_DIR / "log"

# Config
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_CONFIG_DIR = CONFIG_DIR / ".default"

# ABI
ABI_DIR = SCRIPT_DIR / "abi"

# Input
INPUT_DIR = BASE_DIR / "input"

# Database
DATABASES_DIR = INPUT_DIR / ".db"
DATABASE_FILEPATH = DATABASES_DIR / "mintchain.db"
ALEMBIC_INI = BASE_DIR / "alembic.ini"

# Creating dirs and files
_dirs = (INPUT_DIR, DATABASES_DIR, LOG_DIR)

for dirpath in _dirs:
    dirpath.mkdir(exist_ok=True)

# Creating copies
DEFAULT_CONFIG_TOML = DEFAULT_CONFIG_DIR / "config.toml"
CONFIG_TOML = CONFIG_DIR / "config.toml"
copy_file(DEFAULT_CONFIG_TOML, CONFIG_TOML)

DEFAULT_CHAINS_TOML = DEFAULT_CONFIG_DIR / "chains.toml"
CHAINS_TOML = CONFIG_DIR / "chains.toml"
copy_file(DEFAULT_CHAINS_TOML, CHAINS_TOML)
