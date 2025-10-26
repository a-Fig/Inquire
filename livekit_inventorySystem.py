from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import RLock
from typing import Any, Dict, List, Optional

# ✅ Import RunContext from voice.* so LiveKit recognizes it as context
from livekit.agents.voice import RunContext
from livekit.agents import function_tool, llm
from livekit.agents.llm import ToolError


# --------------------------- Data model & store ------------------------------

@dataclass
class Item:
    item_id: str
    name: str
    qty: int = 1
    description: str = ""
    note: str = ""

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


class InventoryStore:
    """Thread-safe single-player inventory."""
    def __init__(self):
        self._inv: Dict[str, Item] = {}
        self._lock = RLock()

    def _require_item(self, item_id: str) -> Item:
        if item_id not in self._inv:
            raise KeyError(f"item '{item_id}' not found")
        return self._inv[item_id]

    def read_inventory(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [it.to_json() for it in self._inv.values()]

    def add_item(self, item_id: str, name: str, qty: int) -> Item:
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


STORE = InventoryStore()


# ----------------------------- Tool helpers ---------------------------------

def _need_str(value: Optional[str], field: str) -> str:
    if value is None or value == "":
        raise ToolError(f"'{field}' is required.")
    return value

def _need_int(value: Optional[int], field: str) -> int:
    if value is None:
        raise ToolError(f"'{field}' is required.")
    return value


# ----------------------------- LiveKit tools --------------------------------

async def _lk_read_inventory(context: RunContext) -> dict:
    """Return the full inventory as JSON list."""
    return {"inventory": STORE.read_inventory()}

async def _lk_add_item(
    context: RunContext,
    item_id: Optional[str] = None,
    name: Optional[str] = None,
    qty: Optional[int] = None,
) -> dict:
    """Add a new item or increment existing quantity.

    Args:
        item_id: Stable ID key.
        name: Human-readable name (defaults to item_id if omitted).
        qty: Units to add (> 0). Defaults to 1 if omitted.
    """
    try:
        item_id = _need_str(item_id, "item_id")
        if name is None or name == "":
            name = item_id
        qty = 1 if qty is None else qty
        item = STORE.add_item(item_id, name, qty)
        return {"status": "added", "item": item.to_json()}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_remove_item(
    context: RunContext,
    item_id: Optional[str] = None,
) -> dict:
    """Remove an item entirely regardless of quantity."""
    try:
        item_id = _need_str(item_id, "item_id")
        STORE.remove_item(item_id)
        return {"status": "removed", "item_id": item_id}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_remove_items(
    context: RunContext,
    item_id: Optional[str] = None,
    qty: Optional[int] = None,
) -> dict:
    """Decrement quantity by qty; deletes item if remainder <= 0."""
    try:
        item_id = _need_str(item_id, "item_id")
        qty = _need_int(qty, "qty")
        item = STORE.remove_items(item_id, qty)
        return {"status": "decremented", "remaining": item.to_json() if item else None}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_set_description(
    context: RunContext,
    item_id: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """Replace the description text for an item."""
    try:
        item_id = _need_str(item_id, "item_id")
        description = _need_str(description, "description")
        item = STORE.set_description(item_id, description)
        return {"status": "updated", "item": item.to_json()}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_get_description(
    context: RunContext,
    item_id: Optional[str] = None,
) -> dict:
    """Read the description for an item."""
    try:
        item_id = _need_str(item_id, "item_id")
        desc = STORE.get_description(item_id)
        return {"item_id": item_id, "description": desc}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_set_note(
    context: RunContext,
    item_id: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """Replace the GM-only note text for an item."""
    try:
        item_id = _need_str(item_id, "item_id")
        note = _need_str(note, "note")
        item = STORE.set_note(item_id, note)
        return {"status": "updated", "item": item.to_json()}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_get_note(
    context: RunContext,
    item_id: Optional[str] = None,
) -> dict:
    """Read the GM-only note for an item."""
    try:
        item_id = _need_str(item_id, "item_id")
        note = STORE.get_note(item_id)
        return {"item_id": item_id, "note": note}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_set_name(
    context: RunContext,
    item_id: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """Rename an item (id stays the same)."""
    try:
        item_id = _need_str(item_id, "item_id")
        name = _need_str(name, "name")
        item = STORE.set_name(item_id, name)
        return {"status": "updated", "item": item.to_json()}
    except Exception as e:
        raise ToolError(str(e))

async def _lk_set_qty(
    context: RunContext,
    item_id: Optional[str] = None,
    qty: Optional[int] = None,
) -> dict:
    """Force quantity to an exact value (0 deletes)."""
    try:
        item_id = _need_str(item_id, "item_id")
        qty = _need_int(qty, "qty")
        item = STORE.set_qty(item_id, qty)
        return {"status": "updated", "item": item.to_json() if item else None}
    except Exception as e:
        raise ToolError(str(e))


# ------------------------- One-call tool factory -----------------------------

def build_livekit_tools() -> list[llm.FunctionTool]:
    """
    Return all inventory tools wrapped for LiveKit.

    Usage:
        tools = build_livekit_tools()
        agent = Agent(instructions="...", tools=tools)
        # or later: await session.update_tools(tools)
    """
    return [
        function_tool(_lk_read_inventory, name="read_inventory",
                      description="Return the full inventory as JSON."),
        function_tool(_lk_add_item, name="add_item",
                      description="Add a new item or increment quantity. Args: item_id, name, qty (>0)."),
        function_tool(_lk_remove_item, name="remove_item",
                      description="Remove an item entirely by item_id."),
        function_tool(_lk_remove_items, name="remove_items",
                      description="Decrement quantity by qty; deletes item if remainder <= 0."),
        function_tool(_lk_set_description, name="set_description",
                      description="Set the description text for an item."),
        function_tool(_lk_get_description, name="get_description",
                      description="Get the description text for an item."),
        function_tool(_lk_set_note, name="set_note",
                      description="Set the GM-only note for an item."),
        function_tool(_lk_get_note, name="get_note",
                      description="Get the GM-only note for an item."),
        function_tool(_lk_set_name, name="set_name",
                      description="Rename an item (id stays the same)."),
        function_tool(_lk_set_qty, name="set_qty",
                      description="Set exact quantity for an item; 0 deletes."),
    ]


if __name__ == "__main__":
    # quick smoke test
    STORE.add_item("stick", "Wooden Stick", 2)
    print(STORE.read_inventory())
