import abc

from kys_in_rest.health.entities.weight import WeightEntry


class WeightRepo(abc.ABC):
    @abc.abstractmethod
    def add_weight_entry(self, entry: WeightEntry) -> None: ...

    @abc.abstractmethod
    def list_weight_entries(self) -> list[WeightEntry]: ...

    @abc.abstractmethod
    def get_last(self) -> WeightEntry | None: ...
