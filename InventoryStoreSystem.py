from typing import Dict, List, Tuple
import json
from dataclasses import dataclass, asdict
from threading import RLock

# -----------------------------------------------------------------------------
# Single‑player inventory tools for your GM LLM. No player_ids anywhere.
# API contract: all tool functions accept List[str] and return (urgent, strJSON).
# -----------------------------------------------------------------------------

@dataclass
class Item:
    item_id: str
    name: str
    qty: int = 1
    description: str = ""
    note: str = ""

    def to_json(self) -> Dict:
        return asdict(self)

class InventoryStore:
    """Thread‑safe single‑player inventory."""
    def __init__(self):
        self._inv: Dict[str, Item] = {}
        self._lock = RLock()

    def _require_item(self, item_id: str) -> Item:
        if item_id not in self._inv:
            raise KeyError(f"item '{item_id}' not found")
        return self._inv[item_id]

    # ---- core ops ------------------------------------------------------------
    def read_inventory(self) -> List[Dict]:
        with self._lock:
            return [it.to_json() for it in self._inv.values()]

    def add_item(self, item_id: str, name: str, qty: int = 1) -> Item:
        if qty <= 0:
            raise ValueError("qty must be positive")
        with self._lock:
            if item_id in self._inv:
                self._inv[item_id].qty += qty
            else:
                self._inv[item_id] = Item(item_id=item_id, name=name, qty=qty)
            return self._inv[item_id]

    def remove_item(self, item_id: str) -> None:
        with self._lock:
            if item_id in self._inv:
                del self._inv[item_id]
            else:
                raise KeyError(f"item '{item_id}' not found")

    def remove_items(self, item_id: str, qty: int) -> Item | None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        with self._lock:
            item = self._require_item(item_id)
            item.qty -= qty
            if item.qty <= 0:
                del self._inv[item_id]
                return None
            return item

    def set_description(self, item_id: str, description: str) -> Item:
        with self._lock:
            item = self._require_item(item_id)
            item.description = description
            return item

    def get_description(self, item_id: str) -> str:
        with self._lock:
            return self._require_item(item_id).description

    def set_note(self, item_id: str, note: str) -> Item:
        with self._lock:
            item = self._require_item(item_id)
            item.note = note
            return item

    def get_note(self, item_id: str) -> str:
        with self._lock:
            return self._require_item(item_id).note

    def set_name(self, item_id: str, name: str) -> Item:
        with self._lock:
            item = self._require_item(item_id)
            item.name = name
            return item

    def set_qty(self, item_id: str, qty: int) -> Item | None:
        if qty < 0:
            raise ValueError("qty must be >= 0")
        with self._lock:
            if qty == 0:
                self.remove_item(item_id)
                return None
            item = self._require_item(item_id)
            item.qty = qty
            return item

# -----------------------------------------------------------------------------
# Toolwrapper adapters (args MUST be strings)
# -----------------------------------------------------------------------------

def ok(payload) -> Tuple[bool, str]:
    return False, json.dumps(payload, ensure_ascii=False)

def urgent(payload) -> Tuple[bool, str]:
    return True, json.dumps(payload, ensure_ascii=False)

STORE = InventoryStore()

# Read entire inventory
def tool_read_inventory(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 0:
        return ok({"error": "usage: read_inventory()"})
    return urgent({"inventory": STORE.read_inventory()})

# Add item (create or increment)

def tool_add_item(args: List[str]) -> Tuple[bool, str]:
    if len(args) < 2 or len(args) > 3:
        return ok({"error": "usage: add_item(item_id, name, [qty])"})
    item_id, name = args[0], args[1]
    qty = int(args[2]) if len(args) == 3 else 1
    try:
        item = STORE.add_item(item_id, name, qty)
        return ok({"status": "added", "item": item.to_json()})
    except Exception as e:
        return urgent({"error": str(e)})

# Remove ALL of an item

def tool_remove_item(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 1:
        return ok({"error": "usage: remove_item(item_id)"})
    item_id = args[0]
    try:
        STORE.remove_item(item_id)
        return ok({"status": "removed", "item_id": item_id})
    except Exception as e:
        return urgent({"error": str(e)})

# Remove a quantity (decrement)

def tool_remove_items(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 2:
        return ok({"error": "usage: remove_items(item_id, qty)"})
    item_id, qty_s = args[0], args[1]
    try:
        qty = int(qty_s)
        item = STORE.remove_items(item_id, qty)
        return ok({"status": "decremented", "remaining": item.to_json() if item else None})
    except Exception as e:
        return urgent({"error": str(e)})

# Set / get description

def tool_set_description(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 2:
        return ok({"error": "usage: set_description(item_id, description)"})
    item_id, description = args
    try:
        item = STORE.set_description(item_id, description)
        return ok({"status": "updated", "item": item.to_json()})
    except Exception as e:
        return urgent({"error": str(e)})

def tool_get_description(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 1:
        return ok({"error": "usage: get_description(item_id)"})
    item_id = args[0]
    try:
        desc = STORE.get_description(item_id)
        return urgent({"item_id": item_id, "description": desc})
    except Exception as e:
        return urgent({"error": str(e)})

# Set / get note

def tool_set_note(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 2:
        return ok({"error": "usage: set_note(item_id, note)"})
    item_id, note = args
    try:
        item = STORE.set_note(item_id, note)
        return ok({"status": "updated", "item": item.to_json()})
    except Exception as e:
        return urgent({"error": str(e)})

def tool_get_note(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 1:
        return ok({"error": "usage: get_note(item_id)"})
    item_id = args[0]
    try:
        note = STORE.get_note(item_id)
        return urgent({"item_id": item_id, "note": note})
    except Exception as e:
        return urgent({"error": str(e)})

# Rename item / set qty

def tool_set_name(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 2:
        return ok({"error": "usage: set_name(item_id, name)"})
    item_id, name = args
    try:
        item = STORE.set_name(item_id, name)
        return ok({"status": "updated", "item": item.to_json()})
    except Exception as e:
        return urgent({"error": str(e)})


def tool_set_qty(args: List[str]) -> Tuple[bool, str]:
    if len(args) != 2:
        return ok({"error": "usage: set_qty(item_id, qty)"})
    item_id, qty_s = args
    try:
        qty = int(qty_s)
        item = STORE.set_qty(item_id, qty)
        return ok({"status": "updated", "item": item.to_json() if item else None})
    except Exception as e:
        return urgent({"error": str(e)})

# -----------------------------------------------------------------------------
# Tool registration helpers for ToolLLM (from tooled_llm.py)
# -----------------------------------------------------------------------------
try:
    from tooled_llm import Toolwrapper
except Exception:  # allow this module to be imported standalone
    class Toolwrapper:  # minimal shim
        def __init__(self, name, action, manual):
            self.name = name; self.action = action; self.manual = manual


def build_tools() -> List[Toolwrapper]:
    """Create Toolwrappers with clear manuals for an LLM using JSON[...]JSON."""
    manuals = {
        "read_inventory": (
            'Action name: "read_inventory"\n'
            'Arguments: []\n'
            'Purpose: Return the full inventory as JSON.\n'
            'Example: JSON[{"action":"read_inventory","args":[]}]JSON'\
        ),
        "add_item": (
            'Action name: "add_item"\n'
            'Arguments: [item_id, name, qty?]  (qty defaults to "1" if omitted)\n'
            'Purpose: Add a new item or increment quantity if it already exists.\n'
            'Example: JSON[{"action":"add_item","args":["stick","Wooden Stick","3"]}]JSON'\
        ),
        "remove_item": (
            'Action name: "remove_item"\n'
            'Arguments: [item_id]\n'
            'Purpose: Remove the item entirely regardless of quantity.\n'
            'Example: JSON[{"action":"remove_item","args":["stick"]}]JSON'\
        ),
        "remove_items": (
            'Action name: "remove_items"\n'
            'Arguments: [item_id, qty]\n'
            'Purpose: Decrement quantity by qty; deletes item if remainder <= 0.\n'
            'Example: JSON[{"action":"remove_items","args":["stick","2"]}]JSON'\
        ),
        "set_description": (
            'Action name: "set_description"\n'
            'Arguments: [item_id, description]\n'
            'Purpose: Replace the description text for an item.\n'
            'Example: JSON[{"action":"set_description","args":["stick","A humble wooden branch."]}]JSON'\
        ),
        "get_description": (
            'Action name: "get_description"\n'
            'Arguments: [item_id]\n'
            'Purpose: Read the description for an item.\n'
            'Example: JSON[{"action":"get_description","args":["stick"]}]JSON'\
        ),
        "set_note": (
            'Action name: "set_note"\n'
            'Arguments: [item_id, note]\n'
            'Purpose: Replace the GM-only note text for an item.\n'
            'Example: JSON[{"action":"set_note","args":["stick","Cursed? glows at dusk."]}]JSON'\
        ),
        "get_note": (
            'Action name: "get_note"\n'
            'Arguments: [item_id]\n'
            'Purpose: Read the GM-only note for an item.\n'
            'Example: JSON[{"action":"get_note","args":["stick"]}]JSON'\
        ),
        "set_name": (
            'Action name: "set_name"\n'
            'Arguments: [item_id, name]\n'
            'Purpose: Rename an item (id stays the same).\n'
            'Example: JSON[{"action":"set_name","args":["stick","Elder Branch"]}]JSON'\
        ),
        "set_qty": (
            'Action name: "set_qty"\n'
            'Arguments: [item_id, qty]\n'
            'Purpose: Force quantity to an exact value ("0" deletes).\n'
            'Example: JSON[{"action":"set_qty","args":["stick","10"]}]JSON'\
        ),
    }

    return [
        Toolwrapper("read_inventory", tool_read_inventory, manuals["read_inventory"]),
        Toolwrapper("add_item", tool_add_item, manuals["add_item"]),
        Toolwrapper("remove_item", tool_remove_item, manuals["remove_item"]),
        Toolwrapper("remove_items", tool_remove_items, manuals["remove_items"]),
        Toolwrapper("set_description", tool_set_description, manuals["set_description"]),
        Toolwrapper("get_description", tool_get_description, manuals["get_description"]),
        Toolwrapper("set_note", tool_set_note, manuals["set_note"]),
        Toolwrapper("get_note", tool_get_note, manuals["get_note"]),
        Toolwrapper("set_name", tool_set_name, manuals["set_name"]),
        Toolwrapper("set_qty", tool_set_qty, manuals["set_qty"]),
    ]

# Optional: quick manual test
if __name__ == "__main__":
    print(json.dumps(STORE.read_inventory()))
    STORE.add_item("stick", "Wooden Stick", 2)
    print(json.dumps(STORE.read_inventory(), indent=2))
