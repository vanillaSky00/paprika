using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;
using NativeWebSocket; // Requires NativeWebSocket package installed

public class AgentNetworkManager : MonoBehaviour
{
    [Header("UI Integration (Optional)")] 
    public AgentThoughtBubble headBubble;  // Bubble above the head

    [Header("Components")]
    public AgentState agentState;           // Must be bound in Inspector
    public AgentNearby agentNearby;         // Must be bound in Inspector

    [Header("Actions")]
    public ActionDispatcher actionDispatcher;   // Must be bound in Inspector

    [Header("Connection Config")]
    // public string serverUrl = "ws://localhost:8000/api/ws/agent/player_1";
    public string serverUrl = "ws://localhost:8000/api/ws/agent/";
    public bool autoReconnect = true;

    [Header("Game State References")]
    public Transform agentTransform;
    // Suggest putting a script reference for action execution here, e.g.:
    // public ActionController actionController; 

    private WebSocket websocket;
    private bool isThinking = false; // Prevent sending duplicate requests while AI is still thinking

    async void Start()
    {
        try
        {
            string uuid = System.Guid.NewGuid().ToString();
            string fullUrl = $"ws://127.0.0.1:8000/api/ws/agent/{uuid}";
            
            headBubble?.ShowThought("Connecting...");
            Debug.Log($"[AI] Initializing connection to: {fullUrl}");
            
            websocket = new WebSocket(fullUrl);

            websocket.OnOpen += () => {
                Debug.Log("<color=green>[AI] Connection Verified by Unity!</color>");
                headBubble?.ShowThought("Connected!");
                StartCoroutine(AgentLoopRoutine());
            };

            websocket.OnError += (e) => {
                Debug.LogError($"[AI] Connection Error: {e}");
                headBubble?.ShowThought("Connection Failed :(");
            };
            websocket.OnClose += (c) => Debug.LogWarning($"[AI] Connection Closed. Code: {c}");

            websocket.OnMessage += (bytes) =>
            {
                // Receive Plan returned from Server
                string message = System.Text.Encoding.UTF8.GetString(bytes);
                HandleServerResponse(message);
            };

            Debug.Log("[AI] Awaiting Connect...");
            await websocket.Connect();
            // Start Perception loop (e.g., every 2 seconds or after action completion)
            StartCoroutine(AgentLoopRoutine());
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[AI] Critical failure during startup: {e.Message}");
        }
    }

    void Update()
    {
        #if !UNITY_WEBGL || UNITY_EDITOR
            websocket.DispatchMessageQueue();
        #endif
    }

    private IEnumerator AgentLoopRoutine()
    {
        while (true)
        {
            // Only send when connection is open and not thinking
            if (websocket.State == WebSocketState.Open && !isThinking)
            {
                SendPerception();
            }
            // maybe dynamic frequency, for different work
            yield return new WaitForSeconds(1.0f); // Adjust frequency
        }
    }

    void HideBubbleDelay()
    {
        headBubble?.HideBubble();
    }
    async void SendPerception()
    {
        isThinking = true;

        headBubble?.ShowThought("(Thinking) Hmm...");

        agentState.GetLastActionStatus(out string status, out string error);
        // 1. Collect scene info (Match this with Python Perception Schema)
        var perception = new PerceptionData
        {
            time_hour = System.DateTime.Now.Hour, // Or in-game time
            day = 1, // Game days
            mode = "reality",
            location_id = agentState.GetLocationId(),

            player_nearby = agentNearby.CheckPlayerNearby(),
            nearby_objects = agentNearby.ScanNearbyObjects(),
            held_item = agentState.GetHeldItem(),
            
            // Important: Report execution result of the last action
            last_action_status = status,
            last_action_error = error
        };
        
        //Debug.Log($"[Sending] Location: {perception.location_id}");
        string json = JsonConvert.SerializeObject(perception);
        await websocket.SendText(json);
    }

    private List<WorldObjectData> ScanNearbyObjects()
    {
        // Example: Search objects within radius
        List<WorldObjectData> objects = new List<WorldObjectData>();
        
        // Assume all interactable objects have "Interactable" Tag
        // This is just an example, write according to actual game logic
        Collider[] hits = Physics.OverlapSphere(agentTransform.position, 5.0f);
        foreach(var hit in hits)
        {
            if(hit.CompareTag("Interactable"))
            {
                objects.Add(new WorldObjectData
                {
                    id = hit.name, // e.g., "Stove_01"
                    type = "Prop",
                    position = new PositionData { x = hit.transform.position.x, y = hit.transform.position.y, z = hit.transform.position.z },
                    distance = Vector3.Distance(agentTransform.position, hit.transform.position),
                    state = "default"
                });
            }
        }
        return objects;
    }

    private void HandleServerResponse(string json)
    {
        Debug.Log("Received Plan: " + json);

        try
        {
            ServerResponse response = JsonConvert.DeserializeObject<ServerResponse>(json);
            
            if (response.plan != null && response.plan.Count > 0)
            {
                Debug.Log($"[Agent] Received task: {response.task}, Total steps: {response.plan.Count}");
                // Start coroutine to execute step by step
                StartCoroutine(ExecutePlanRoutine(response.plan));
            }
            else
            {
                headBubble?.HideBubble();
                Debug.Log("[Agent] Received response but no plan (Chatting or Thinking)");
                isThinking = false; // Nothing to do, unlock thinking directly
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Parsing Error: " + e.Message);
            isThinking = false; // Unlock even on error
        }
    }
    private IEnumerator ExecutePlanRoutine(List<AgentActionData> plan)
    {
        foreach (var action in plan)
        {
            headBubble?.ShowThought(action.thought_trace);

            Debug.Log($"[Agent] Start executing step: {action.function} ({action.thought_trace})");
            
            // 1. Raise flag "I am busy" before execution
            // This prevents Manager from continuing immediately regardless of Move (Async) or Put (Sync)
            agentState.IsActionExecuting = true;

            // 2. Dispatch command to ActionMove / ActionPut
            actionDispatcher.DispatchAction(action.function, action.args);
            
            // 3. Smart wait: Wait as long as Agent is busy (IsActionExecuting == true)
            // Set a timeout safeguard (e.g., 30s) to prevent infinite stuck if bugs occur
            float timeout = 30f; 
            float timer = 0f;

            while (agentState.IsActionExecuting && timer < timeout)
            {
                yield return null; // Wait for next frame (Won't freeze Unity)
                timer += Time.deltaTime;
            }

            // If exited due to timeout, print warning
            if (timer >= timeout) 
            {
                Debug.LogWarning($"[Agent] Warning: Action {action.function} exceeded {timeout}s, forcing next step!");
                agentState.IsActionExecuting = false; // Force reset
            }

            // 4. Small buffer between actions (Make movement look less stiff)
            yield return new WaitForSeconds(0.5f); 
        }

        Debug.Log("[Agent] All plans finished! (Task Finished)");
        
        headBubble?.ShowThought("Finished!");
        isThinking = false; 
        // SendPerception(); // Uncomment if continuous thinking is needed
    }
    private async void OnApplicationQuit()
    {
        if(websocket != null) await websocket.Close();
    }
    private void OnDestroy()
    {
        StopAllCoroutines();
    }
    [ContextMenu("Debug: Print Current Perception")]
    public void DebugPrintCurrentPerception()
    {
        // 1. Get data (Copy logic from SendPerception, but don't send)
        agentState.GetLastActionStatus(out string status, out string error);
        
        var perception = new PerceptionData
        {
            time_hour = System.DateTime.Now.Hour,
            day = 1,
            mode = "reality",
            location_id = agentState.GetLocationId(),
            player_nearby = agentNearby.CheckPlayerNearby(),
            nearby_objects = agentNearby.ScanNearbyObjects(), // Ensure no error here
            held_item = agentState.GetHeldItem(),
            last_action_status = status,
            last_action_error = error
        };

        // 2. Serialize and print
        string json = JsonConvert.SerializeObject(perception, Formatting.Indented);
        Debug.Log($"<color=yellow>[Debug Check] Current Perception State:</color>\n{json}");
    }

    [ContextMenu("Test: Chop Onion -> Put on Plate")]
    public void TestMockChopOnion_Final()
    {
        // 1. Scene object names (Confirm these names exist in Hierarchy)
        string onionSource = "OnionBox";     // Place to get onion
        string tableLocation = "Preparation"; // Prep table (Navigate here)
        string functionalBoard = "CutBoard";  // Cutting board (On prep table, has SliceBoard script)
        string plateLocation = "Plate";       // Plate (Place for final product)

        // 2. Safety check
        if (GameObject.Find(functionalBoard) == null)
        {
            Debug.LogError($"[Test Error] Cannot find '{functionalBoard}'! Check if it exists in scene with correct name.");
            return;
        }

        Debug.Log($"[Test] Start flow: {onionSource} -> {tableLocation}(Stand) -> {functionalBoard}(Chop) -> {plateLocation}");

        // 3. Compose command
        string mockJson = $@"
        {{
            ""task"": ""Chop onion and plate it"",
            ""plan"": [
                {{
                    ""thought_trace"": ""1. Go get onion"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{onionSource}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. Pickup onion"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{onionSource}"" }}
                }},
                {{
                    ""thought_trace"": ""3. Walk to table"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{functionalBoard}"" }}
                }},
                {{
                    ""thought_trace"": ""4. Put on cut board"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{functionalBoard}"" }}
                }},
                {{
                    ""thought_trace"": ""5. Chop chop chop"",
                    ""function"": ""chop"",
                    ""args"": {{ ""id"": ""{functionalBoard}"" }}
                }},
                {{
                    ""thought_trace"": ""6. Pick up chopped onion"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{functionalBoard}"" }}
                }},
                {{
                    ""thought_trace"": ""7. Move to plate"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""8. Plating"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableLocation}"" }}
                }}
            ]
        }}";

        HandleServerResponse(mockJson);
    }
    [ContextMenu("Test: Meat -> Oven -> Table (Separated Flow)")]
    public void TestMockCookMeat_Final()
    {
        string meatSource = "MeatBox";      
        string ovenLocation = "Oven";       
        string tableLocation = "Preparation"; 

        if (GameObject.Find(ovenLocation) == null)
        {
            Debug.LogError($"[Test Error] Cannot find '{ovenLocation}'!");
            return;
        }

        Debug.Log($"[Test] Start flow: Get Raw -> Put into Oven -> Wait Cook -> Get Cooked -> Table");

        string mockJson = $@"
        {{
            ""task"": ""Cook meat completely"",
            ""plan"": [
                {{
                    ""thought_trace"": ""1. Go to MeatBox"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{meatSource}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. Pick up raw meat"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{meatSource}"" }}
                }},
                {{
                    ""thought_trace"": ""3. Go to Oven"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{ovenLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""4. Put meat in Oven"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{ovenLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""5. Wait for cooking..."",
                    ""function"": ""cook"",
                    ""args"": {{ ""id"": ""{ovenLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""6. Pick up cooked meat"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{ovenLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""7. Go to Prep Table"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableLocation}"" }}
                }},
                {{
                    ""thought_trace"": ""8. Place cooked meat"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableLocation}"" }}
                }}
            ]
        }}";

        HandleServerResponse(mockJson);
    }
    [ContextMenu("Test: Simulate Server Command (Mock-Tomato ID Version)")]
    public void TestMockTomatoServerResponse()
    {
        // 1. Set scene object names (Confirm objects with these names exist)
        string itemName = "MeatBox";      // Item to take
        string tableName = "";

        // 2. Safety check (Ensure object exists, otherwise ActionMove won't find it)
        if (GameObject.Find(itemName) == null)
        {
            Debug.LogError($"[Test Error] Cannot find '{itemName}'! Check scene object names");
            return;
        }

        Debug.Log($"[Test] Start Tomato Transport Test (ID Mode): {itemName} -> {tableName}");

        // 3. Fabricate JSON command (No coordinate numbers)
        // Note: move_to args changed to use "id"
        string mockJson = $@"
        {{
            ""task"": ""Deliver tomato to counter (Test)"",
            ""plan"": [
                {{
                    ""thought_trace"": ""1. Go to Tomato Box"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{itemName}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. Pickup Tomato"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{itemName}"" }}
                }},
                {{
                    ""thought_trace"": ""3. Go to counter with tomato"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }},
                {{
                    ""thought_trace"": ""4. Put tomato on counter"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }}
            ]
        }}";

        // 4. Send command
        HandleServerResponse(mockJson);
    }
}

// --- Data Classes (DTOs) Matches Python Schemas ---

[Serializable]
public class PerceptionData
{
    public int time_hour;
    public int day;
    public string mode; // "reality", "dream"
    public string location_id;
    public bool player_nearby;

    public List<WorldObjectData> nearby_objects;
    public string held_item;
    public string last_action_status;
    public string last_action_error;
}

[Serializable]
public class WorldObjectData
{
    public string id;
    public string type;
    public PositionData position;
    public float distance;
    public string state;
}

[Serializable]
public class PositionData
{
    public float x, y, z;
}

[Serializable]
public class ServerResponse
{
    public string client_id;
    public string task;
    public List<AgentActionData> plan;
}

[Serializable]
public class AgentActionData
{
    public string thought_trace;
    public string function; // "move_to", "interact", etc.
    public Dictionary<string, object> args; // Arguments
    public bool plan_complete;
}