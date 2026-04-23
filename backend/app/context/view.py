"""
Philosophy: Instead of telling the LLM "if X is on CutBoard, you must chop",
we inject the live perception string "A Tomato is on the CutBoard. You MUST
chop it immediately." The rule becomes an unavoidable physical reality, not an
abstract instruction that competes with everything else in the context window.

Architecture:
    ObservationAdapter   - thin accessor layer over the Pydantic Perception model.
                           Kept for backward compatibility with existing callers.
    KitchenRegistry      - canonical, Python-owned knowledge of items, stations,
                           tables, and processing rules. Does NOT trust Unity
                           naming alone.
    PerceptionRenderer   - builds the 5-component affordance context
                           (Self / Affordances / Kitchen / Memory / Failure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from app.api.schemas import Perception


# =============================================================================
#  KitchenRegistry  --  Python-owned domain knowledge
# =============================================================================
#
#  The original plan's `is_processed()` was left empty. We fill it here with a
#  hard-coded registry rather than relying on string heuristics, because Unity
#  naming is inconsistent:
#    - Containers emit uppercase raw names:     MEATBALL, TOMATO, ONION
#    - Stations emit mixed-case processed names: CookedMeat, TomatoSlice
#    - Preparation tables come as:               Preparation1..4  (shared)
#                                                Player_preparation_1..2 (personal)
#
#  Centralising this here means agents and renderers never re-derive it.
# =============================================================================

# Raw ingredient names as they appear inside container.state.held_item
RAW_INGREDIENTS: frozenset[str] = frozenset({
    "MEATBALL", "TOMATO", "ONION", "LETTUCE", "CHEESE", "BREAD",
})

# Processed ingredient names as they appear after chopping or cooking
PROCESSED_INGREDIENTS: frozenset[str] = frozenset({
    "CookedMeat",
    "TomatoSlice", "OnionSlice", "LettuceSlice", "CheeseSlice", "BreadSlice",
})

# Station processing rules: ingredient -> (station_id, action)
PROCESSING_RULES: dict[str, tuple[str, str]] = {
    "MEATBALL": ("Oven",     "cook"),
    "TOMATO":   ("CutBoard", "chop"),
    "ONION":    ("CutBoard", "chop"),
    "LETTUCE":  ("CutBoard", "chop"),
    "CHEESE":   ("CutBoard", "chop"),
    "BREAD":    ("CutBoard", "chop"),
}

# Object classification by id prefix / exact match
CONTAINER_BOXES: frozenset[str] = frozenset({
    "MeatBox", "TomatoBox", "OnionBox", "LettuceBox", "CheeseBox", "BreadBox",
})
STATIONS: frozenset[str] = frozenset({"Oven", "CutBoard", "PlateBoard", "Trash"})

# Canonical preparation-table IDs. Naming differs between the two types
# and the LLM tends to "normalise" them into a single pattern — e.g.
# emitting `Preparation_1` (wrong) because it matches the player form.
# Keep these as ordered tuples so they render predictably in the prompt.
SHARED_PREP_TABLES: tuple[str, ...] = (
    "Preparation1", "Preparation2", "Preparation3", "Preparation4",
)
PLAYER_PREP_TABLES: tuple[str, ...] = (
    "Player_preparation_1", "Player_preparation_2",
)

# Hamburger assembly order — PLACEMENT order on a Player_preparation table,
# first placement = bottom bun, last placement = top bun. Uses the Unity
# *processed* ingredient names (what the agent actually holds after a
# chop / cook action).
HAMBURGER_STACK: tuple[str, ...] = (
    "BreadSlice",    # bottom bun
    "CheeseSlice",
    "OnionSlice",
    "LettuceSlice",
    "TomatoSlice",
    "CookedMeat",
    "BreadSlice",    # top bun
)


def is_processed(item_name: Optional[str]) -> bool:
    """Return True if the given item name refers to a processed ingredient.

    Unity is inconsistent: the same item shows up as `CookedMeat` in some
    fields, `COOKEDMEAT` in `state.held_item`, and `SLICED_BREAD` or
    `SLICEDBREAD` in `statistics.table_items`. We accept all of these.
    """
    if not item_name:
        return False
    if item_name in PROCESSED_INGREDIENTS:
        return True
    upper = item_name.upper().replace("_", "")
    return any(marker in upper for marker in ("COOKED", "SLICE", "GRATED"))


def is_raw(item_name: Optional[str]) -> bool:
    """Return True if the given item name refers to a raw ingredient."""
    if not item_name:
        return False
    return item_name in RAW_INGREDIENTS


def is_shared_prep_table(object_id: str) -> bool:
    """`Preparation1`..`Preparation4` are the shared assembly tables."""
    return object_id.startswith("Preparation") and not object_id.startswith("Player_")


def is_player_prep_table(object_id: str) -> bool:
    """`Player_preparation_1`..`Player_preparation_2` are personal hand-off zones."""
    return object_id.startswith("Player_preparation")


def processing_target_for(ingredient: str) -> Optional[tuple[str, str]]:
    """Return (station_id, action_verb) for a raw ingredient, or None."""
    return PROCESSING_RULES.get(ingredient)


# =============================================================================
#  HeldItem  --  canonical inventory representation
# =============================================================================

@dataclass(frozen=True)
class HeldItem:
    """Typed representation of what the agent is currently holding.

    Why a dataclass? The Unity schema for `self.held_item` has wobbled between
    a string, a nested object, and null. Agents should never touch that raw
    field; they consume this stable shape instead.
    """
    name: str
    is_raw: bool
    is_processed: bool

    @property
    def is_empty_hands(self) -> bool:
        return self.name == "Nothing"

    @classmethod
    def empty(cls) -> "HeldItem":
        return cls(name="Nothing", is_raw=False, is_processed=False)

    @classmethod
    def from_raw(cls, raw) -> "HeldItem":
        """Build from whatever self.held_item turns out to be.

        Accepted shapes:
          - None / missing
          - "MEATBALL" (bare string)
          - {"id": "...", "name": "MEATBALL", "tags": [...]}
        """
        if raw is None:
            return cls.empty()
        if isinstance(raw, str):
            name = raw
        elif isinstance(raw, dict):
            name = raw.get("name") or raw.get("id") or "Unknown"
        else:  # pydantic nested model or similar
            name = getattr(raw, "name", None) or getattr(raw, "id", "Unknown")

        return cls(
            name=name,
            is_raw=is_raw(name),
            is_processed=is_processed(name),
        )


# =============================================================================
#  ObservationAdapter  --  thin, backward-compatible access layer
# =============================================================================

class ObservationAdapter:
    """
    Why: The schema of Perception raw data often varies. ObservationAdapter
    decouples the system from the evolving Unity schema.

    This class is kept intentionally thin. All *formatting* for LLM consumption
    lives in PerceptionRenderer below.
    """

    def __init__(self, perception: Perception):
        self._p = perception

    # ---- primitive accessors --------------------------------------------

    @property
    def location(self) -> str:
        return self._p.self.current_zone

    @property
    def time_display(self) -> str:
        return f"{self._p.self.time_hour}:00"

    @property
    def held_item(self) -> HeldItem:
        return HeldItem.from_raw(getattr(self._p.self, "held_item", None))

    @property
    def inventory(self) -> str:
        """Back-compat: returns 'Nothing' or the item name."""
        return self.held_item.name

    @property
    def reachable(self) -> list:
        return list(self._p.sensory.reachable_objects)

    @property
    def visible(self) -> list:
        return list(self._p.sensory.visible_objects)

    # ---- legacy summary strings (unchanged contracts) -------------------

    @property
    def visual_summary(self) -> str:
        reachables = self.reachable
        visibles = self.visible
        all_objs = reachables + visibles
        if not all_objs:
            return "I see nothing interactable nearby"

        results = []
        for o in all_objs:
            prefix = "[Reachable] " if o in reachables else ""
            results.append(f"{prefix}{o.id}{getattr(o, 'status_summary', '')}")
        return ", ".join(results)

    @property
    def last_execution_summary(self) -> str:
        trace = self._p.execution_trace
        if not trace:
            return "None"
        for step in trace:
            if step.status != "success":
                return f"❌ FAILED at Step {step.step_index}: {step.message}"
        return f"✅ SUCCESS (Completed {len(trace)} steps)"

    @property
    def prepared_items_summary(self) -> str:
        stats = self._p.statistics
        if not stats or stats.table_item_count == 0:
            return "Preparation Tables are empty."
        return (
            f"We have prepared those ingredients "
            f"({stats.table_item_count} items): {', '.join(stats.table_items)}"
        )


# =============================================================================
#  PerceptionRenderer  --  affordance-driven context builder
# =============================================================================
#
#  This is the "context engineering" layer. Each render_* method produces ONE
#  component of the five-part perception block. The master function
#  build_perception_context() assembles them all.
#
#  Downstream, the SAME block is fed to Curriculum, Actor, AND Critic so they
#  cannot disagree about kitchen state. skill.md (Scribe) bypasses this and
#  gets the raw trace separately.
# =============================================================================

# Object ids that should never be treated as inventory/supply (plates, trash)
INFRASTRUCTURE_IDS: frozenset[str] = frozenset({"Trash", "PlateBoard"})


class PerceptionRenderer:
    """Converts a Perception snapshot into the 5-component affordance block."""

    def __init__(self, perception: Perception):
        self.obs = ObservationAdapter(perception)
        self._p = perception

    # ---- [A] SELF STATE -------------------------------------------------

    def render_self_state(self) -> str:
        held = self.obs.held_item
        if held.is_empty_hands:
            return "Your hands are empty. You are free to pick up ingredients."

        qualifier = []
        if held.is_raw:
            qualifier.append("Raw")
        if held.is_processed:
            qualifier.append("Processed")
        tag_str = f" ({', '.join(qualifier)})" if qualifier else ""

        return (
            f"You are currently holding {held.name}{tag_str}. "
            f"Your hands are full; you must place this down before picking up anything else."
        )

    # ---- [B] IMMEDIATE AFFORDANCES --------------------------------------

    def render_reachable_affordances(self) -> str:
        """Translate each reachable object into what the agent can do with it."""
        held = self.obs.held_item
        lines: list[str] = []

        for obj in self.obs.reachable:
            line = self._affordance_for(obj, held)
            if line:
                lines.append(line)

        return "\n".join(lines) if lines else "- No interactable objects within reach. Move first."

    def _affordance_for(self, obj, held: HeldItem) -> Optional[str]:
        """Dispatch on object id / type. One rule per station — this is where
        the old PHYSICS RULES block lived."""
        oid = obj.id
        state = getattr(obj, "state", {}) or {}
        if hasattr(state, "model_dump"):      # pydantic BaseModel
            state = state.model_dump()
        elif hasattr(state, "dict"):           # pydantic v1
            state = state.dict()

        # --- Oven ---------------------------------------------------------
        if oid == "Oven":
            return self._oven_affordance(state, held)

        # --- CutBoard -----------------------------------------------------
        if oid == "CutBoard":
            return self._cutboard_affordance(state, held)

        # --- Container boxes ---------------------------------------------
        if oid in CONTAINER_BOXES:
            return self._container_affordance(oid, state, held)

        # --- Preparation tables (shared + player) ------------------------
        if is_shared_prep_table(oid) or is_player_prep_table(oid):
            return self._prep_table_affordance(oid, state, held)

        # --- Trash --------------------------------------------------------
        if oid == "Trash":
            if not held.is_empty_hands and held.is_raw:
                return f"- The Trash is here. You can discard your raw {held.name} here if it is no longer needed."
            return None

        # --- PlateBoard ---------------------------------------------------
        if oid == "PlateBoard":
            if held.is_processed:
                return f"- The PlateBoard has a PLATE. You can assemble your {held.name} onto a plate here."
            return None

        return None

    # ---- per-station affordance logic -----------------------------------

    def _oven_affordance(self, state: dict, held: HeldItem) -> str:
        held_on_oven = state.get("held_item")
        has_cooked = state.get("has_cooked_food")

        # Cooked meat ready to collect — HIGHEST priority
        if has_cooked or held_on_oven == "CookedMeat":
            return "- The Oven has finished cooking. CookedMeat is ready — PICK IT UP now."

        # Something is on it but not done yet
        if held_on_oven and held_on_oven != "CookedMeat":
            return f"- The Oven has {held_on_oven} on it. Wait for it to finish cooking."

        # Empty oven + meatball in hand = exact match
        if held.name == "MEATBALL":
            return "- The Oven is empty and ready. Put your MEATBALL here to cook it."

        # Empty oven, agent not carrying meat
        return "- The Oven is empty and ready to receive a MEATBALL."

    def _cutboard_affordance(self, state: dict, held: HeldItem) -> str:
        occupied_by = state.get("occupied_by") or state.get("held_item")

        if occupied_by and occupied_by not in PROCESSED_INGREDIENTS:
            return (
                f"- The CutBoard holds a raw {occupied_by}. "
                f"You MUST chop it immediately — do not leave it raw."
            )

        if occupied_by and occupied_by in PROCESSED_INGREDIENTS:
            return f"- The CutBoard holds a finished {occupied_by}. Pick it up and move it to a Preparation table."

        # Empty board
        if held.is_raw and held.name != "MEATBALL":
            return f"- The CutBoard is empty. Put your {held.name} here to chop it."

        return "- The CutBoard is empty. Bring a raw vegetable or bread here to chop."

    def _container_affordance(self, oid: str, state: dict, held: HeldItem) -> Optional[str]:
        item_name = state.get("held_item")
        if state.get("is_empty"):
            return f"- The {oid} is empty."

        # Supply check: skip sources whose processed form already exists on a prep table
        stats = self._p.statistics
        table_items = list(getattr(stats, "table_items", []) or []) if stats else []
        if self._already_prepared(item_name, table_items):
            return f"- The {oid} still has {item_name}, but a processed version is already on the prep table — do NOT gather more."

        if not held.is_empty_hands:
            return f"- The {oid} has {item_name} available, but your hands are full. Put down your current item first."

        return f"- The {oid} has {item_name} ready to pick up."

    def _prep_table_affordance(self, oid: str, state: dict, held: HeldItem) -> Optional[str]:
        occupied = state.get("is_occupied") or state.get("held_item") is not None
        item_on_table = state.get("held_item")

        if is_player_prep_table(oid):
            return self._player_prep_affordance(oid, item_on_table, occupied, held)
        return self._shared_prep_affordance(oid, item_on_table, occupied, held)

    def _shared_prep_affordance(
        self, oid: str, item_on_table, occupied: bool, held: HeldItem,
    ) -> Optional[str]:
        """Preparation1..Preparation4 — short-term parking for processed
        ingredients. NOT the assembly table."""
        if occupied and item_on_table:
            if is_processed(item_on_table):
                return f"- {oid} holds a prepared {item_on_table}. Leave it here until burger assembly."
            if is_raw(item_on_table):
                return (
                    f"- {oid} holds a RAW {item_on_table}. This is clutter — "
                    f"pick it up and either process it or trash it."
                )
            return f"- {oid} holds {item_on_table}."

        # Empty table
        if held.is_processed:
            return f"- {oid} is empty. You can park your {held.name} here until it's time to assemble the burger."
        if held.is_raw:
            return (
                f"- {oid} is empty. You MAY temporarily drop {held.name} here to free your hands, "
                f"but raw items should be processed, not stored here."
            )
        return None  # empty table, empty hands → nothing worth saying

    def _player_prep_affordance(
        self, oid: str, item_on_table, occupied: bool, held: HeldItem,
    ) -> Optional[str]:
        """Player_preparation_N — primary use: burger assembly in strict
        stack order. Secondary use: overflow storage when every shared
        Preparation table is occupied."""
        stack_str = " → ".join(HAMBURGER_STACK)

        if occupied and item_on_table:
            if is_processed(item_on_table):
                return (
                    f"- {oid} has {item_on_table} on the stack. Burger order (bottom→top): "
                    f"{stack_str}. Add the next missing layer if you are holding it."
                )
            if is_raw(item_on_table):
                return (
                    f"- {oid} has a RAW {item_on_table} on it — wrong. This table is for "
                    f"burger assembly; pick it up and process or trash it."
                )
            return f"- {oid} holds {item_on_table}."

        # Empty table
        if held.name == "BreadSlice":
            return (
                f"- {oid} is empty — place your BreadSlice here as the BOTTOM bun to start a "
                f"burger. Stack order (bottom→top): {stack_str}."
            )
        if held.is_processed:
            return (
                f"- {oid} is empty. This is an assembly table; the stack must start with a "
                f"BreadSlice bun (you are holding {held.name}). Park {held.name} on a shared "
                f"Preparation table until the bun is down."
            )
        if held.is_raw:
            return f"- {oid} is empty and is for burger assembly — raw items do not belong here."
        return (
            f"- {oid} is empty and ready for burger assembly. Fetch a BreadSlice to start. "
            f"Stack order (bottom→top): {stack_str}."
        )

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _already_prepared(raw_name: Optional[str], table_items: Iterable[str]) -> bool:
        """True if a processed form of `raw_name` already exists in table_items."""
        if not raw_name:
            return False
        raw_to_processed = {
            "MEATBALL": "COOKEDMEAT",
            "TOMATO":   "TOMATOSLICE",
            "ONION":    "ONIONSLICE",
            "LETTUCE":  "LETTUCESLICE",
            "CHEESE":   "CHEESESLICE",
            "BREAD":    "BREADSLICE",
        }
        target = raw_to_processed.get(raw_name, "").upper()
        return any(target in str(t).upper() for t in table_items)

    # ---- [C] KITCHEN STATE (supply check, raw vs processed) -------------

    def render_supply_check(self) -> str:
        """Primary source: live held_item on each prep table we can see.
        Fallback: Unity's `statistics.table_items` aggregate when no prep
        table is in sight. Unity does not reliably populate the aggregate
        every frame, so we cannot trust "empty stats = empty tables"."""

        seen: list[tuple[str, str]] = []  # (table_id, item_name)
        for obj in self.obs.reachable + self.obs.visible:
            if not (is_shared_prep_table(obj.id) or is_player_prep_table(obj.id)):
                continue
            state = getattr(obj, "state", {}) or {}
            if hasattr(state, "model_dump"):
                state = state.model_dump()
            elif hasattr(state, "dict"):
                state = state.dict()
            held = state.get("held_item")
            if held:
                seen.append((obj.id, str(held)))

        parts: list[str] = []
        if seen:
            processed = [(t, i) for (t, i) in seen if is_processed(i)]
            raw = [(t, i) for (t, i) in seen if is_raw(i) and not is_processed(i)]
            other = [(t, i) for (t, i) in seen if not is_processed(i) and not is_raw(i)]

            if processed:
                listing = ", ".join(f"{i} @ {t}" for (t, i) in processed)
                parts.append(
                    f"READY ingredients (do NOT re-gather or re-prepare): {listing}."
                )
            if raw:
                listing = ", ".join(f"{i} @ {t}" for (t, i) in raw)
                parts.append(
                    f"WARNING — RAW items on prep tables (must be trashed or processed): {listing}."
                )
            if other:
                listing = ", ".join(f"{i} @ {t}" for (t, i) in other)
                parts.append(f"Other items on prep tables: {listing}.")

        # Fallback: Unity's aggregate, but only when we can't see any prep
        # table ourselves — otherwise the live observation is authoritative.
        stats = self._p.statistics
        unity_items = list(getattr(stats, "table_items", []) or []) if stats else []
        if not seen and unity_items:
            processed_agg = [t for t in unity_items if self._table_entry_is_processed(t)]
            raw_agg = [t for t in unity_items if not self._table_entry_is_processed(t)]
            if processed_agg:
                parts.append(
                    f"READY ingredients (Unity aggregate, no prep table in sight): {', '.join(processed_agg)}."
                )
            if raw_agg:
                parts.append(
                    f"WARNING — RAW items reported on prep tables (Unity aggregate): {', '.join(raw_agg)}."
                )

        base = "\n".join(parts) if parts else (
            "No prep-table contents observed. Either no prepared ingredients "
            "yet, or no prep table is currently visible from here."
        )

        # Keep the legacy stray-scan as a defensive belt-and-braces — it
        # fires only when a visible prep table holds a raw item AND the
        # code above somehow missed it.
        stray = self._scan_stray_raw_on_tables()
        if stray and not any("WARNING" in p for p in parts):
            base += f"\nStray raw items spotted on tables: {', '.join(stray)}."

        return base

    @staticmethod
    def _table_entry_is_processed(entry: str) -> bool:
        """Table entries look like 'COOKEDMEAT:1' or 'SLICED_ONION:1'."""
        name = entry.split(":", 1)[0].upper()
        processed_markers = ("COOKED", "SLICE", "SLICED", "GRATED")
        return any(marker in name for marker in processed_markers)

    def _scan_stray_raw_on_tables(self) -> list[str]:
        out: list[str] = []
        for obj in self.obs.reachable + self.obs.visible:
            if not (is_shared_prep_table(obj.id) or is_player_prep_table(obj.id)):
                continue
            state = getattr(obj, "state", {}) or {}
            if hasattr(state, "model_dump"):
                state = state.model_dump()
            held = state.get("held_item")
            if held and is_raw(held):
                out.append(f"{held}@{obj.id}")
        return out

    # ---- [D] SHORT-TERM MEMORY ------------------------------------------

    def render_history(self, window: int = 4) -> str:
        trace = list(getattr(self._p, "execution_trace", []) or [])
        if not trace:
            return "No recent actions."

        recent = trace[-window:]
        lines: list[str] = []
        for step in recent:
            action = f"{step.function} on {step.target_id}"
            if step.status == "success":
                lines.append(f"- ✅ {action} — {step.message}")
            else:
                lines.append(f"- ❌ {action} FAILED — {step.message}")
        return "\n".join(lines)

    # ---- [E] FAILURE CONTEXT (unified retry block) ----------------------

    def render_failure_context(self, retry_count: int = 0, current_task: str = "") -> str:
        trace = list(getattr(self._p, "execution_trace", []) or [])
        last_failure = next(
            (s for s in reversed(trace) if s.status != "success"),
            None,
        )

        if last_failure is None and retry_count == 0:
            return "No recent failures. Proceed with the plan."

        lines = [f"Consecutive failures on current goal: {retry_count}"]
        if last_failure is not None:
            lines.append(
                f"Last failure reason: {last_failure.message} "
                f"(on {last_failure.function} → {last_failure.target_id})"
            )
            lines.append(f"Suggested correction: {self._correction_hint(last_failure)}")

        if retry_count >= 2:
            lines.append(
                "⚠ Retry threshold reached. STOP retrying this approach. "
                "Either choose an alternate route/target, or abandon this sub-goal and ask the Mentor for a new task."
            )
        return "\n".join(lines)

    @staticmethod
    def _correction_hint(step) -> str:
        msg = (step.message or "").lower()
        if "too far" in msg or "out of range" in msg:
            return f"Move closer to {step.target_id} before retrying."
        if "path blocked" in msg or "unreachable" in msg:
            return f"Try an alternate route or pick an intermediate waypoint on the way to {step.target_id}."
        if "hands full" in msg or "holding" in msg:
            return "Put down your current item on the nearest Preparation table first."
        if "empty" in msg:
            return f"{step.target_id} is empty — pick a different source."
        return "Re-examine the perception block and choose a different action."

    # ---- [LAYOUT] CANONICAL OBJECT IDs ----------------------------------
    #
    # Static per-game reference. Kept in the perception block (not the
    # system prompt) so every agent sees the exact strings Unity expects,
    # even when the target isn't currently in sight.

    @staticmethod
    def render_kitchen_layout() -> str:
        stack_str = " → ".join(HAMBURGER_STACK)
        return (
            "Use these EXACT strings as target_id — do not rename, pluralise, "
            "or add/remove underscores:\n"
            f"- Stations: {', '.join(sorted(STATIONS))}\n"
            f"- Ingredient boxes: {', '.join(sorted(CONTAINER_BOXES))}\n"
            f"- Shared prep tables, for PARKING processed ingredients "
            f"(NO underscore): {', '.join(SHARED_PREP_TABLES)}\n"
            f"- Player hand-off tables, for BURGER ASSEMBLY "
            f"(WITH underscore, lowercase 'p'): {', '.join(PLAYER_PREP_TABLES)}\n"
            f"Burger stack — place on a Player table in THIS order "
            f"(bottom→top): {stack_str}.\n"
            "If all shared prep tables are occupied, a Player table may be used "
            "as temporary overflow, but assembly is its primary purpose."
        )

    # ---- MASTER ASSEMBLY ------------------------------------------------

    def build_perception_context(
        self,
        retry_count: int = 0,
        current_task: str = "",
    ) -> str:
        """Produce the single markdown block injected into all three active agents."""
        return (
            "### [LAYOUT] CANONICAL OBJECT IDs\n"
            f"{self.render_kitchen_layout()}\n\n"
            "### [A] SELF STATE\n"
            f"{self.render_self_state()}\n\n"
            "### [B] IMMEDIATE AFFORDANCES (what you can do right now)\n"
            f"{self.render_reachable_affordances()}\n\n"
            "### [C] KITCHEN STATE (supply check)\n"
            f"{self.render_supply_check()}\n\n"
            "### [D] SHORT-TERM MEMORY (recent actions)\n"
            f"{self.render_history()}\n\n"
            "### [E] FAILURE CONTEXT\n"
            f"{self.render_failure_context(retry_count=retry_count, current_task=current_task)}"
        )


# =============================================================================
#  Module-level convenience
# =============================================================================

def build_perception_context(
    perception: Perception,
    retry_count: int = 0,
    current_task: str = "",
) -> str:
    """Shortcut used by LangGraph nodes."""
    return PerceptionRenderer(perception).build_perception_context(
        retry_count=retry_count,
        current_task=current_task,
    )