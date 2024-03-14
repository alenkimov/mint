import pandas as pd
import numpy as np
from pathlib import Path


def create_csv(dirpath: Path, name: str, columns) -> Path:
    default_csv_filepath = dirpath / f"{name}.csv"
    df = pd.DataFrame(columns=columns)
    df.to_csv(default_csv_filepath, index=False)
    return default_csv_filepath


def load_csv(csv_filepath: Path) -> pd.DataFrame:
    return pd.read_csv(csv_filepath).replace({np.nan: None})


def get_csv_filenames(dirpath: Path) -> list[str]:
    csv_filepath_generator = dirpath.glob("*.csv")
    return [csv_filepath.name for csv_filepath in csv_filepath_generator]
