from app.api.schemas import Perception


class ObservationAdapter:
    """
    Why: The schema of Perception raw data often varies due to granuality of prompts engineering test.
    How: ObservationAdapter helps decouple the system by defined interaction with Perception.
    """
    def __init__(self, perception: Perception):
        # We now accept the STRICT Pydantic model
        self._p = perception

    @property
    def location(self) -> str:
        return self._p.self.current_zone

    @property
    def time_display(self) -> str:
        return f"{self._p.self.time_hour}:00"

    @property
    def inventory(self) -> str:
        item = self._p.self.held_item
        # Accessing nested dict keys safely or just returning the name
        if item and "id" in item:
            return item["id"]
        return "Nothing"

    @property
    def visual_summary(self) -> str:
        objs = self._p.sensory.visible_objects
        if not objs:
            return "I see nothing interactable nearby"
        
        # The logic is now cleaner because .status_summary does the work
        # Output: "Stove(is_on,contains_items), Tomato(default)"
        return ", ".join([f"{o.id}{o.status_summary}" for o in objs])

    @property
    def last_execution_summary(self) -> str:
        """
        Give the summary of last action set, the summary should be combined with short-term memory 
        TODO: Should test if this information is completed enough for llm to understand the last action sets
        """
        trace = self._p.execution_trace
        if not trace:
            return "None"

        # Scan for the first failure using dot notation
        for step in trace:
            if step.status != "success":
                return f"❌ FAILED at Step {step.step_index}: {step.message}"

        return f"✅ SUCCESS (Completed {len(trace)} steps)"