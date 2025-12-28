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
                SendPerception();
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
            // 開始發送 Perception 的循環 (例如每 2 秒或是動作執行完後)
            // StartCoroutine(AgentLoopRoutine());
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[AI] Critical failure during startup: {e.Message}");
        }
    }

    void Update()
    {
        #if !UNITY_WEBGL || UNITY_EDITOR
            if (websocket != null) 
            {
                websocket.DispatchMessageQueue();
            }
        #endif

        // Periodic check in console every 60 frames
        // if (Time.frameCount % 60 == 0 && websocket != null)
        // {
        //     Debug.Log($"[AI] Current Live State: {websocket.State}");
        // }
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
            //location_id = agentState.GetLocationId(),
            location_id = "kitchen",
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
                    //position = new PositionData { x = hit.transform.position.x, y = hit.transform.position.y, z = hit.transform.position.z },
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
            Debug.Log($"[Agent] 開始執行步驟: {action.function} ({action.thought_trace})");
            
            // 1. 在執行前，先舉起旗標「我正在忙」
            // 這樣不管是 Move (非同步) 還是 Put (同步)，Manager 都不會馬上往下跑
            agentState.IsActionExecuting = true;

            // 2. 發送指令給 ActionMove / ActionPut
            actionDispatcher.DispatchAction(action.function, action.args);
            
            // 3. 智能等待：只要 Agent 還在忙 (IsActionExecuting == true)，就一直等
            // 設定一個超時保險 (例如 30秒)，避免如果出 Bug 卡死一輩子
            float timeout = 30f; 
            float timer = 0f;

            while (agentState.IsActionExecuting && timer < timeout)
            {
                yield return null; // 等待下一幀 (不會卡住 Unity)
                timer += Time.deltaTime;
            }

            // 如果是因為超時才跳出來的，印個警告
            if (timer >= timeout) 
            {
                Debug.LogWarning($"[Agent] 警告：動作 {action.function} 執行超過 {timeout} 秒，強制跳到下一步！");
                agentState.IsActionExecuting = false; // 強制重置
            }

            // 4. 動作之間的小緩衝 (讓動作看起來不那麼僵硬)
            yield return new WaitForSeconds(0.5f); 
        }

        Debug.Log("[Agent] 所有計畫執行完畢！(Task Finished)");
        
        isThinking = false; 
        // SendPerception(); // 如果需要連續思考可以打開
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
        // 1. 設定場景物件名稱
        string itemName = "OnionBox";       // 要拿的
        string tableName = "Preparation"; // 要放的

        // 2. 防呆檢查 (只是為了確保場景沒壞，不需要取座標了)
        if (GameObject.Find(itemName) == null)
        {
            Debug.LogError($"[Test Error] 找不到 '{itemName}'！請檢查場景物件名稱");
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
        // 1. 設定場景物件名稱 (請確認場景裡真的有這些名字的物件)
        string itemName = "TomatoBox";      // 要拿的東西
        string tableName = "Preparation"; // 要放的桌子

        // 2. 防呆檢查 (確保場景有這東西，不然 ActionMove 也會找不到)
        if (GameObject.Find(itemName) == null)
        {
            Debug.LogError($"[Test Error] 找不到 '{itemName}'！請檢查場景物件名稱");
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
    //public PositionData position;
    public float distance;
    public string state;
}

/*[Serializable]
public class PositionData
{
    public float x, y, z;
}*/

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