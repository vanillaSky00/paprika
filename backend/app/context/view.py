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
#  Hard-coded registry rather than relying on string heuristics, because Unity
#  naming is inconsistent:
#    - Containers emit uppercase raw names:      MEATBALL, TOMATO, ONION
#    - Stations emit mixed-case processed names: CookedMeat, TomatoSlice
#    - Preparation tables come as:               Preparation1..4  (shared)
#                                                Player_preparation_1..2 (personal)
#
#  Centralising this here means agents and renderers never re-derive it.
# =============================================================================


RAW_INGREDIENTS: frozenset[str] = frozenset({
    "MEATBALL", "TOMATO", "ONION", "LETTUCE", "CHEESE", "BREAD",
})
PROCESSED_INGREDIENTS: frozenset[str] = frozenset({
    "CookedMeat",
    "TomatoSlice", "OnionSlice", "LettuceSlice", "CheeseSlice", "BreadSlice",
})
PROCESSING_RULES: dict[str, tuple[str, str]] = {
    "MEATBALL": ("Oven",     "cook"),
    "TOMATO":   ("CutBoard", "chop"),
    "ONION":    ("CutBoard", "chop"),
    "LETTUCE":  ("CutBoard", "chop"),
    "CHEESE":   ("CutBoard", "chop"),
    "BREAD":    ("CutBoard", "chop"),
}
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

# Where the PLATE starts each game. It is NOT the assembly surface —
# the agent picks the plate up here, carries it to a parking table,
# puts it down, and that table becomes the assembly surface.
PLATE_SOURCE: str = "PlateBoard"

# Hamburger assembly order — PLACEMENT order onto the plate.
HAMBURGER_STACK: tuple[str, ...] = (
    "BreadSlice",    # 1st placement — top bun of finished burger
    "CookedMeat",
    "TomatoSlice",
    "LettuceSlice",
    "OnionSlice",
    "CheeseSlice",
    "BreadSlice",    # 7th placement — bottom bun of finished burger
)


def is_plate(item_name: str | None) -> bool:
    """True if the named item refers to a PLATE (case-insensitive)."""
    if not item_name:
        return False
    return item_name.strip().upper() == "PLATE"


def is_processed(item_name: str | None) -> bool:
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

        # --- PlateBoard (assembly target) --------------------------------
        if oid == "PlateBoard":
            return self._plate_affordance(state, held)

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

        # Every box yields a RAW ingredient. Spell that out so the LLM
        # doesn't confuse e.g. BREAD (raw) with BreadSlice (processed).
        process_verb = "cooked on the Oven" if item_name == "MEATBALL" else "chopped on the CutBoard"
        if not held.is_empty_hands:
            return (
                f"- The {oid} has RAW {item_name} available (must be {process_verb} "
                f"before it can be used), but your hands are full. "
                f"Put down your current item first."
            )
        return (
            f"- The {oid} has RAW {item_name} ready to pick up. It MUST be "
            f"{process_verb} before it can go on a plate."
        )

    def _prep_table_affordance(self, oid: str, state: dict, held: HeldItem) -> Optional[str]:
        """Preparation1..4 and Player_preparation_1..2 are
        interchangeable surfaces that serve two roles:
        (a) PARKING for processed ingredients, or
        (b) the ASSEMBLY SURFACE — if the PLATE has been placed here,
            all subsequent burger layers are stacked here.
        Role is decided per-table by whether held_item == PLATE."""
        item_on_table = state.get("held_item")
        stack_str = " → ".join(HAMBURGER_STACK)

        # Table currently holds the PLATE → this is the assembly surface.
        if is_plate(item_on_table):
            if held.name == "BreadSlice":
                return (
                    f"- {oid} has the PLATE — this is the ASSEMBLY SURFACE. "
                    f"Place your BreadSlice here as the FIRST layer (top bun "
                    f"of the finished burger). Order: {stack_str}."
                )
            if held.is_processed:
                return (
                    f"- {oid} has the PLATE — assembly surface. Assembly must "
                    f"start with a BreadSlice (you are holding {held.name}). "
                    f"Park {held.name} on another table first, then fetch a BreadSlice."
                )
            if held.name == "PLATE":
                return f"- {oid} already has a PLATE. Don't stack plates; go prep a BreadSlice."
            if held.is_raw:
                process_hint = "Oven" if held.name == "MEATBALL" else "CutBoard"
                return (
                    f"- {oid} has the PLATE — but you are holding RAW {held.name}. "
                    f"RAW ingredients NEVER go on the plate. Take it to {process_hint} "
                    f"to process first, then come back."
                )
            return (
                f"- {oid} has the PLATE — this is the ASSEMBLY SURFACE. "
                f"Fetch a BreadSlice to start. Order: {stack_str}."
            )

        # Table holds a non-plate item. Unity reports only the TOP item,
        # so a "BreadSlice" here is ambiguous between "parked BreadSlice"
        # and "BreadSlice just placed on a plate that's underneath".
        # Describe truthfully and let the agent reason from [D] history.
        if item_on_table:
            if is_processed(item_on_table):
                return (
                    f"- {oid} shows {item_on_table} on top. If this table is "
                    f"your assembly surface (see [D] history for the PLATE put_down), "
                    f"stack the next layer here; otherwise it's a parked ingredient."
                )
            if is_raw(item_on_table):
                return (
                    f"- {oid} holds a RAW {item_on_table}. This is clutter — "
                    f"pick it up and either process it or trash it."
                )
            return f"- {oid} holds {item_on_table}."

        # Empty table.
        if held.name == "PLATE":
            return f"- {oid} is empty. `put_down` the PLATE here to set up the burger assembly surface."
        if held.is_processed:
            return f"- {oid} is empty. You can park your {held.name} here, or take it to the plated table if one exists."
        if held.is_raw:
            return (
                f"- {oid} is empty. You MAY temporarily drop {held.name} here to free your hands, "
                f"but raw items should be processed, not stored here."
            )
        return None  # empty table, empty hands → nothing worth saying

    def _plate_affordance(self, state: dict, held: HeldItem) -> str:
        """PlateBoard is the SOURCE of the PLATE, not the assembly
        surface. Agent picks the plate up here, carries it to any
        Preparation<N> or Player_preparation_<N>, and puts it down —
        that table becomes the assembly surface."""
        on_board = state.get("held_item")

        if not is_plate(on_board):
            return (
                "- PlateBoard has no PLATE available. Check the parking tables "
                "for an already-placed plate (the assembly surface)."
            )

        # PlateBoard has a PLATE ready to take.
        if held.is_empty_hands:
            return (
                "- PlateBoard has a PLATE. `pickup` it here, then carry it to "
                "any Preparation<N> or Player_preparation_<N> and `put_down` — "
                "that table becomes the burger assembly surface."
            )
        if held.name == "PLATE":
            return "- PlateBoard still shows a PLATE, but you're already holding one. Go put yours down on a table."
        return (
            f"- PlateBoard has a PLATE, but your hands are full with {held.name}. "
            f"Park {held.name} first, then return for the plate."
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
            plated_tables = [t for (t, i) in seen if is_plate(i)]
            processed = [(t, i) for (t, i) in seen if is_processed(i) and not is_plate(i)]
            raw = [(t, i) for (t, i) in seen if is_raw(i) and not is_processed(i)]
            other = [
                (t, i) for (t, i) in seen
                if not is_processed(i) and not is_raw(i) and not is_plate(i)
            ]

            if plated_tables:
                parts.append(
                    f"ASSEMBLY SURFACE: {', '.join(plated_tables)} has the PLATE — "
                    "stack burger layers here in order."
                )
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
        fn = getattr(step, "function", "") or ""
        target = getattr(step, "target_id", "") or ""

        if "too far" in msg or "out of range" in msg:
            return (
                f"Move closer to {target} before retrying. Plan an extra "
                f"`move_to {target}` ahead of the next `{fn} {target}`."
            )
        if "path blocked" in msg or "unreachable" in msg:
            return f"Try an alternate route or pick an intermediate waypoint on the way to {target}."

        # Distinguish between the two 'empty' failure modes:
        #   - `put_down` with empty hands → a prior `pickup` silently
        #     failed (Unity's `move_to` sometimes reports success while
        #     leaving the agent slightly out of pickup range). Recovery
        #     is to repeat the `move_to` before retrying `pickup`.
        #   - `pickup` from an empty source → the container/table ran
        #     out; pick a different source.
        if fn == "put_down" and ("empty" in msg or "nothing" in msg):
            return (
                "Hands are empty at put_down — your earlier `pickup` "
                "silently failed (Unity's `move_to` may report success "
                "while leaving you slightly out of pickup range). In your "
                "retry plan, repeat the `move_to <source>` immediately "
                "before `pickup <source>` to re-approach, then carry on "
                "to the downstream steps."
            )
        if fn == "pickup" and "empty" in msg:
            return f"{target} is empty — pick a different source."
        if "hands full" in msg or "holding" in msg:
            return "Put down your current item on the nearest parking table first."
        if "empty" in msg:
            # Last-resort fallback — unknown "empty" message on a
            # non-pickup / non-put_down step. Kept to avoid losing the
            # original heuristic coverage.
            return f"{target} is empty — pick a different source."
        return "Re-examine the perception block and choose a different action."

    # ---- [LAYOUT] CANONICAL OBJECT IDs ----------------------------------
    #
    # Static per-game reference. Kept in the perception block (not the
    # system prompt) so every agent sees the exact strings Unity expects,
    # even when the target isn't currently in sight.

    @staticmethod
    def render_kitchen_layout() -> str:
        stack_str = " → ".join(HAMBURGER_STACK)
        parking = SHARED_PREP_TABLES + PLAYER_PREP_TABLES
        raw_names = ", ".join(sorted(RAW_INGREDIENTS))
        return (
            "Use these EXACT strings as target_id — do not rename, pluralise, "
            "or add/remove underscores:\n"
            f"- Stations: {', '.join(sorted(STATIONS))}\n"
            f"- Ingredient boxes: {', '.join(sorted(CONTAINER_BOXES))}\n"
            f"- Parking / assembly tables (interchangeable): "
            f"{', '.join(parking)}\n"
            f"- PlateBoard: the SOURCE of the PLATE. Assembly does NOT happen here.\n"
            "\n"
            "INGREDIENT NAMES — RAW vs PROCESSED (these are DIFFERENT items):\n"
            f"  RAW       (come from boxes, cannot go on plate): {raw_names}\n"
            "  PROCESSED (come from stations, valid for plate): BreadSlice, "
            "CheeseSlice, OnionSlice, LettuceSlice, TomatoSlice, CookedMeat.\n"
            "MEATBALL becomes CookedMeat via the Oven; every other raw item "
            "becomes a <Name>Slice via the CutBoard. Raw → processed is a "
            "REQUIRED station step.\n"
            "\n"
            "BURGER ASSEMBLY FLOW (3 phases):\n"
            "1. PLATE SETUP — `move_to PlateBoard` → `pickup PlateBoard` → "
            "`move_to <any parking table>` → `put_down <that table>`. "
            "That table is now the ASSEMBLY SURFACE.\n"
            "2. PREP — for each burger layer, `<Box> → Station → process → "
            "pickup → put_down on any other parking table` (short-term park).\n"
            "3. STACK — carry each processed ingredient from its parking "
            "table to the plated table and `put_down` in this order:\n"
            f"   {stack_str}.\n"
            "Bread is placed TWICE. FIRST placement is the TOP bun of the "
            "finished burger; LAST placement is the BOTTOM bun."
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
            f"{self.render_failure_context(retry_count=retry_count, current_task=current_task)}\n\n"
            "### [F] ASSEMBLY PROGRESS (authoritative — reported by Unity)\n"
            f"{self._render_assembly_progress()}"
        )

    def _render_assembly_progress(self) -> str:
        """Unity owns the plate state machine and publishes it as
        `perception.assembly`. We just format it.

        Unity does NOT visualize stacked layers on the plated table via
        its held_item (that stays "PLATE"); this section remains the
        only source-of-truth for stack progress — do not cross-check
        against [B] or [C]."""
        assembly = getattr(self._p, "assembly", None)
        if assembly is None:
            return (
                "No plate set up yet. First required task: PLATE_SETUP — "
                "pick up the PLATE from PlateBoard and put it on any parking table."
            )

        plate = getattr(assembly, "plate_location", None)
        stack = list(getattr(assembly, "stack", []) or [])
        next_expected = getattr(assembly, "next_expected", None)
        is_done = bool(getattr(assembly, "is_done", False))

        if not plate:
            return (
                "No plate set up yet. First required task: PLATE_SETUP — "
                "pick up the PLATE from PlateBoard and put it on any parking table."
            )
        if is_done:
            placed_str = " → ".join(stack) if stack else "(complete)"
            return (
                f"Burger COMPLETE on {plate}: {placed_str}. Pick up the finished "
                f"burger or start a new PLATE_SETUP on a different parking table."
            )
        if not stack:
            first = next_expected or "BreadSlice"
            return (
                f"Plate is set up at {plate} — waiting for the first layer "
                f"({first})."
            )
        placed_str = " → ".join(stack)
        progress = len(stack)
        next_hint = f" Next expected layer: {next_expected}." if next_expected else ""
        return (
            f"Plated table: {plate}. Placed so far ({progress}): {placed_str}."
            f"{next_hint}"
        )


# =============================================================================
#  Module-level convenience
# =============================================================================

def build_perception_context(
    perception: Perception,
    retry_count: int = 0,
    current_task: str = "",
) -> str:
    """Shortcut used by LangGraph nodes / the FastAPI route."""
    return PerceptionRenderer(perception).build_perception_context(
        retry_count=retry_count,
        current_task=current_task,
    )