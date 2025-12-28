```
{
  "self": {
    "time_hour": 22,
    "location_id": "Cooking_Area",  // <--- NEW: Replaces vague location_id
    "status": "Idle",                // Idle, Moving, Interacting
    "held_item": {                   // <--- NEW: Object instead of just string
       "id": "Meatball_01",
       "name": "Meatball",
       "tags": ["Raw", "Food"],      // Critical context: "Raw" means it needs cooking
       "temperature": "Cold"
    }
  },
  "sensory": {
    "player_nearby": true,
    
    // Split objects into two lists to help agent decide "Interact" vs "Move"
    "reachable_objects": [           // Objects close enough to touch NOW (< 1.5m)
       {
         "id": "Oven",
         "type": "Station",
         "state": {                  // <--- NEW: Real granular context
            "is_on": true,
            "is_occupied": false,    // Crucial: Can I put my meatball in?
            "cooking_progress": 0
         }
       },
       {
         "id": "MeatBox",
         "type": "Container",
         "state": {
            "is_empty": false        // Agent knows it can still get meat
         }
       }
    ],
    
    "visible_objects": [             // Objects visible but require movement
       {
         "id": "CutBoard",
         "type": "Station",
         "distance": 5.7,
         "state": {
            "occupied_by": "Onion"   // Crucial: Agent knows NOT to bring meat here
         }
       },
       {
         "id": "Plate_player_1",
         "type": "Plate",
         "distance": 2.6,
         "state": {
            "ready_to_serve": false
         }
       }
    ]
  },
  "execution_trace": [
    {
      "step_index": 1,
      "function": "move_to",
      "target_id": "MeatBox",
      "status": "success",
      "message": "Arrived at destination."
    },
    {
      "step_index": 2,
      "function": "pickup",
      "target_id": "MeatBox",
      "status": "success",
      "message": "Item 'Raw Meat' added to inventory."
    },
    {
      "step_index": 3,
      "function": "move_to",
      "target_id": "Oven",
      "status": "failed",
      "message": "Path blocked / Target unreachable."
    }
  ]
}
```