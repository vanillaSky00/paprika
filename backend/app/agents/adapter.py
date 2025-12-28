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

        reachables = self._p.sensory.reachable_objects
        visibles = self._p.sensory.visible_objects
        

        all_objs = reachables + visibles
        if not all_objs:
            return "I see nothing interactable nearby"
        

        results = []
        for o in all_objs:
            prefix = "[Reachable] " if o in reachables else ""
            results.append(f"{prefix}{o.id}{o.status_summary}")
            
        return ", ".join(results)

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
    
    @property
    def prepared_items_summary(self) -> str:
        """
        Returns a summary of processed ingredients currently on the Preparation Tables.
        Useful for the Curriculum Agent to know if 'Assembly' can start.
        """
        stats = self._p.statistics
        
        if not stats or stats.table_item_count == 0:
            return "Preparation Tables are empty."
        
        # 2. Format the list
        # Input: ["SLICED_ONION:1", "COOKEDMEAT:1"]
        # Output: "SLICED_ONION(1), COOKEDMEAT(1)"
        formatted_items = ", ".join(stats.table_items)
        
        return f"We have prepared those ingredients ({stats.table_item_count} items): {formatted_items}"