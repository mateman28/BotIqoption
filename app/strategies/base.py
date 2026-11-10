from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, m1_df: pd.DataFrame, m5_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[str], Dict]:
        """
        Analyzes candle data and generates a trading signal.
        Returns:
            Tuple of (Signal, Info_Dict)
            Signal can be: 'CALL', 'PUT', or None
        """
        pass
