from abc import ABC, abstractmethod


class BaseActuator(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def on(self) -> None: ...

    @abstractmethod
    async def off(self) -> None: ...

    async def close(self) -> None:
        pass
