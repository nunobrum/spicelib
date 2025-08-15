import dataclasses
import enum
from copy import deepcopy
from typing import Union

UpdateValueType = Union[str, int, float, None]


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

    def __repr__(self):
        if self.updates == UpdateType.UpdateParameter:
            return f"Parameter {self.name} was updated to {self.value}"
        elif self.updates == UpdateType.UpdateComponentValue:
            return f"Component {self.name} value was updated to {self.value}"
        elif self.updates == UpdateType.UpdateComponentParameter:
            return f"Parameter {self.name} was updated to {self.value}"
        elif self.updates == UpdateType.DeleteParameter:
            return f"Parameter {self.name} was deleted"
        elif self.updates == UpdateType.DeleteComponent:
            return f"Component {self.name} was deleted"
        elif self.updates == UpdateType.DeleteComponentParameter:
            return f"Component Parameter {self.name} was deleted"
        elif self.updates == UpdateType.DeleteInstruction:
            return f"Instruction \"{self.value}\" was deleted"
        elif self.updates == UpdateType.AddParameter:
            return f"Parameter {self.name} was added with {self.value}"
        elif self.updates == UpdateType.AddComponent:
            return f"Component {self.name} was added"
        elif self.updates == UpdateType.AddComponentParameter:
            return f"Component Parameter {self.name} was added with value {self.value}"
        elif self.updates == UpdateType.AddInstruction:
            return f"Instruction \"{self.value}\" was added."
        elif self.updates == UpdateType.CloneSubcircuit:
            return f"Sub-circuit {self.name} was added"
        else:
            return "Invalid Update"


class Updates:
    """A list of updates done to a Netlist"""
    def __init__(self):
        self.netlist_updates: list[Update] = []

    def __copy__(self):
        newone = type(self)()
        newone.netlist_updates = deepcopy(self.netlist_updates)
        return newone

    def __len__(self):
        return len(self.netlist_updates)

    def __getitem__(self, item: Union[int, slice, str]) -> Union[Update, list[Update]]:
        if isinstance(item, (int, slice)):
            return self.netlist_updates[item]  # with item = slice, we could get a list here. Otherwise, it is a single Update
        elif isinstance(item, str):
            # Try to get it by name
            for update in self.netlist_updates:
                if update.name == item:
                    return update
            raise IndexError(f"The item {item} doesn't exit.")
        else:
            raise TypeError("getitem only supports int, slice and str")

    def clear(self):
        """Clear the list of updates."""
        self.netlist_updates.clear()

    def add_update(self, name: str, value: UpdateValueType, updates: UpdateType):
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

    def value(self, reference) -> UpdateValueType:
        "Get the value update done to a component. Returns None if there wasn't any update."
        for update in self.netlist_updates:
            if update.updates == UpdateType.UpdateComponentValue and update.name == reference:
                return update.value

    def parameter(self, name):
        "Get the update done to a parameter. Returns None if there wasn't any update."
        for update in self.netlist_updates:
            if update.updates in (UpdateType.UpdateParameter, UpdateType.AddParameter) and name == update.name:
                return update.value
