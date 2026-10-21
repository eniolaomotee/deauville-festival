"""Where the festival lives. The rest of the program only knows the interface."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from .errors import StorageError
from .festival import Festival


class Storage(ABC):
    """load() gives the festival, save() keeps it. How is the storage's business."""

    @abstractmethod
    def load(self) -> Festival: ...

    @abstractmethod
    def save(self, festival: Festival) -> None: ...


class JsonStorage(Storage):
    """The festival in one JSON file, data/festival.json by default."""

    def __init__(self, path: str | Path = "data/festival.json") -> None:
        self.path = Path(path)

    def load(self) -> Festival:
        try:
            with open(self.path, encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise StorageError(f"{self.path} is not found") from None
        except json.JSONDecodeError as error:
            raise StorageError(
                f"{self.path} is damaged: {error.msg} at line {error.lineno}, "
                f"column {error.colno}"
            ) from None
        return Festival.from_data(data)

    def save(self, festival: Festival) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(festival.to_data(), file, indent=2, ensure_ascii=False)
                file.write("\n")
        except OSError as error:
            raise StorageError(f"{self.path} cannot be written: {error}") from None


class MemoryStorage(Storage):
    """Nothing on disk, for tests. Keeps the data, not the objects, like a file."""

    def __init__(self, festival: Festival) -> None:
        self._data = festival.to_data()

    def load(self) -> Festival:
        return Festival.from_data(self._data)

    def save(self, festival: Festival) -> None:
        self._data = festival.to_data()
