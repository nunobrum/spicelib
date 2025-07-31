import dataclasses
import enum
from copy import deepcopy
from typing import Union, List, Optional

UpdateValueType = Union[str, int, float]


class UpdateType(enum.Enum):
    """The UpdateType holds the information about what is being updated."""
    InvalidUpdate = 0
    UpdateParameter = enum.auto()
    UpdateComponentValue = enum.auto()
    UpdateComponentParameter = enum.auto()
    DeleteParameter = enum.auto()
    DeleteComponent = enum.auto()
    DeleteComponentParameter = enum.auto()
    DeleteInstruction = enum.auto()
    AddParameter = enum.auto()
    AddComponent = enum.auto()
    AddComponentParameter = enum.auto()
    AddInstruction = enum.auto()
    CloneSubcircuit = enum.auto()


@dataclasses.dataclass
class Update:
    """An object containing an update element."""
    name: str
    value: UpdateValueType
    updates: UpdateType = UpdateType.InvalidUpdate


class Updates:
    """A list of updates done to a Netlist"""
    def __init__(self):
        self.netlist_updates: List[Update] = []

    def __copy__(self):
        newone = type(self)()
        newone.netlist_updates = deepcopy(self.netlist_updates)
        return newone

    def __len__(self):
        return len(self.netlist_updates)

    def __getitem__(self, item):
        return self.netlist_updates[item]

    def clear(self):
        """Clear the list of updates."""
        self.netlist_updates.clear()

    def add_update(self, name: str, value: Optional[UpdateValueType], updates: UpdateType):
        """Add an update to the list"""
        for update in self.netlist_updates:
            if (update.name == name and
                    (name != "INSTRUCTION" or value == update.value) and  # if instruction then it should match
                    (update.updates == updates or updates == UpdateType.InvalidUpdate)):
                break
        else:
            update = Update(name, value, updates)
            self.netlist_updates.append(update)
        if updates != UpdateType.InvalidUpdate:
            update.updates = updates
        update.value = value
        return update

    def value(self, reference) -> Optional[UpdateValueType]:
        "Get the value update done to a component. Returns None if there wasn't any update."
        for update in self.netlist_updates:
            if update.updates == UpdateType.UpdateComponentValue and update.name == reference:
                return update.value

    def parameter(self, name):
        "Get the update done to a parameter. Returns None if there wasn't any update."
        for update in self.netlist_updates:
            if update.updates in (UpdateType.UpdateParameter, UpdateType.AddParameter) and name == update.name:
                return update.value
