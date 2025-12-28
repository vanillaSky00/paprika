using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;
using NativeWebSocket;

public class AgentNetworkManager : MonoBehaviour
{
    [Header("UI Integration")] 
    public AgentThoughtBubble headBubble;

    [Header("Components")]
    public AgentState agentState;
    public AgentNearby agentNearby; // 用來取得視覺半徑參數
    public ActionDispatcher actionDispatcher;

    [Header("Connection Config")]
    public string serverUrl = "ws://localhost:8000/api/ws/agent/";
    
    [Header("Runtime Data")]
    // 儲存動作歷史紀錄
    public List<ExecutionTraceItem> traceHistory = new List<ExecutionTraceItem>();
    
    // 用來記錄當前是 Plan 的第幾步
    private int currentStepIndex = 0;

    private WebSocket websocket;
    private bool isThinking = false;

    async void Start()
    {
        try
        {
            string uuid = System.Guid.NewGuid().ToString();
            string fullUrl = $"{serverUrl}{uuid}"; 
            
            headBubble?.ShowThought("Connecting...");
            Debug.Log($"[AI] Connecting to: {fullUrl}");
            
            websocket = new WebSocket(fullUrl);

            websocket.OnOpen += () => {
                Debug.Log("<color=green>[AI] Connected!</color>");
                headBubble?.ShowThought("Connected!");
                StartCoroutine(AgentLoopRoutine());
            };

            websocket.OnError += (e) => {
                Debug.LogError($"[AI] Error: {e}");
                headBubble?.ShowThought("Connection Failed");
            };
            
            websocket.OnMessage += (bytes) =>
            {
                string message = System.Text.Encoding.UTF8.GetString(bytes);
                HandleServerResponse(message);
            };

            await websocket.Connect();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[AI] Critical failure: {e.Message}");
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
            if (websocket.State == WebSocketState.Open && !isThinking)
            {
                SendPerception();
            }
            yield return new WaitForSeconds(1.0f); 
        }
    }

    // ------------------------------------------------------------------------
    // 1. 發送感知 (組裝 JSON)
    // ------------------------------------------------------------------------
    async void SendPerception()
    {
        isThinking = true;

        AgentPayload payload = new AgentPayload();

        // A. Self
        payload.self = BuildSelfData();

        // B. Sensory
        payload.sensory = BuildSensoryData();

        // C. Execution Trace (只傳最近 5 筆)
        if (traceHistory.Count > 5)
            payload.execution_trace = traceHistory.GetRange(traceHistory.Count - 5, 5);
        else
            payload.execution_trace = new List<ExecutionTraceItem>(traceHistory);

        string json = JsonConvert.SerializeObject(payload, Formatting.Indented);
        await websocket.SendText(json);
    }

    // ------------------------------------------------------------------------
    // 2. 構建 Self Data
    // ------------------------------------------------------------------------
    private SelfData BuildSelfData()
    {
        SelfData data = new SelfData();
        data.time_hour = 22; 
        data.status = agentState.IsActionExecuting ? "Interacting" : "Idle";
        data.current_zone = "kitchen";

        Inventory inv = GetComponent<Inventory>();
        if (inv != null && inv.CurrentType != ItemType.NONE)
        {
            // 修正點：先宣告一個具體的 HeldItemData 變數 (tempItem)
            HeldItemData tempItem = new HeldItemData();
            
            // 在這個具體變數上設定數值
            tempItem.id = inv.CurrentType.ToString() + "_01";
            tempItem.name = inv.CurrentType.ToString();
            tempItem.tags = new List<string>();

            if (inv.CurrentType == ItemType.MEATBALL) {
                tempItem.tags.Add("Raw");
                tempItem.tags.Add("Food");
                tempItem.temperature = "Cold";
            }
            else if (inv.CurrentType == ItemType.COOKEDMEAT) {
                tempItem.tags.Add("Food");
                tempItem.tags.Add("Cooked");
                tempItem.temperature = "Hot";
            }
            else {
                tempItem.tags.Add("Item");
                tempItem.temperature = "Neutral";
            }
        
            //  最後再把填好的 tempItem 賦值給 object 型別的欄位
            data.held_item = tempItem;
        }
        else
        {
            // 這裡賦值字串 "none"，也是合法的，因為目標是 object
            data.held_item = "none";
        }

        return data;
    }

    // ------------------------------------------------------------------------
    // 3. 構建 Sensory Data (掃描環境)
    // ------------------------------------------------------------------------
    private SensoryData BuildSensoryData()
    {
        SensoryData data = new SensoryData();
        data.player_nearby = (agentNearby != null && agentNearby.CheckPlayerNearby());
        data.reachable_objects = new List<WorldObjectData>();
        data.visible_objects = new List<WorldObjectData>();

        float radius = (agentNearby != null) ? agentNearby.visionRadius : 5.0f;
        Collider[] hits = Physics.OverlapSphere(transform.position, radius);

        foreach (var hit in hits)
        {
            // 只處理有特定 Component 的物件
            if (IsInterestingObject(hit.gameObject))
            {
                WorldObjectData objData = new WorldObjectData();
                objData.id = hit.name;
                // objData.distance = Vector3.Distance(transform.position, hit.transform.position);
                Vector3 closestPoint = hit.ClosestPoint(transform.position);
                objData.distance = Vector3.Distance(transform.position, closestPoint);
                objData.type = DetermineObjectType(hit.gameObject);
                
                // 🔥 取得詳細狀態 (Dictionary)
                objData.state = GetObjectDetailedState(hit.gameObject);

                // 分類：可觸及 (1.5m) vs 可見
                if (objData.distance <= 2.5f)
                    data.reachable_objects.Add(objData);
                else
                    data.visible_objects.Add(objData);
            }
        }

        return data;
    }

    // 過濾感興趣的物件
    private bool IsInterestingObject(GameObject obj)
    {
        return obj.GetComponent<Oven>() != null || 
               obj.GetComponent<ItemBox>() != null || 
               obj.GetComponent<SliceBoard>() != null ||
               obj.name.Contains("Plate");
    }

    private string DetermineObjectType(GameObject obj)
    {
        if (obj.GetComponent<Oven>() || obj.GetComponent<SliceBoard>()) return "Station";
        if (obj.GetComponent<ItemBox>()) return "Container";
        if (obj.name.Contains("Plate")) return "Plate";
        return "Interactable";
    }

    // 🔥 核心：取得物件的詳細狀態
    private Dictionary<string, object> GetObjectDetailedState(GameObject obj)
    {
        var state = new Dictionary<string, object>();

        // Oven
        if (obj.TryGetComponent<Oven>(out Oven oven))
        {
            state["is_on"] = true;
            OvenBox box = obj.GetComponentInChildren<OvenBox>();
            if (box != null)
            {
                // canTake 代表煮好了，GetItem()!=NONE 代表有東西佔著
                state["is_occupied"] = (!box.canTake && box.GetItem() != ItemType.NONE);
                state["has_cooked_food"] = box.canTake;
                //state["cooking_progress"] = 0; // 這裡可以接 oven.progress
            }
        }
        // MeatBox / OnionBox
        else if (obj.TryGetComponent<ItemBox>(out ItemBox itemBox))
        {
            state["is_empty"] = false; 
        }
        // CutBoard
        else if (obj.TryGetComponent<SliceBoard>(out SliceBoard board))
        {
            if (board.CurrentType != ItemType.NONE)
                state["occupied_by"] = board.CurrentType.ToString(); 
            else
                state["occupied_by"] = "none";
        }
        // Plate
        else if (obj.name.Contains("Plate"))
        {
            state["ready_to_serve"] = false;
        }

        return state;
    }

    // ------------------------------------------------------------------------
    // 4. 紀錄 Action Trace
    // ------------------------------------------------------------------------
    public void RecordActionTrace(string functionName, string target, bool success, string msg)
    {
        ExecutionTraceItem item = new ExecutionTraceItem();
        item.step_index = (currentStepIndex > 0) ? currentStepIndex : traceHistory.Count + 1;
        item.function = functionName;
        item.target_id = target;
        item.status = success ? "success" : "failed";
        item.message = msg;
        
        traceHistory.Add(item);
    }

    // ------------------------------------------------------------------------
    // 5. 處理 Server 回應
    // ------------------------------------------------------------------------
    private void HandleServerResponse(string json)
    {
        try
        {
            ServerResponse response = JsonConvert.DeserializeObject<ServerResponse>(json);
            if (response.plan != null && response.plan.Count > 0)
            {
                StartCoroutine(ExecutePlanRoutine(response.plan));
            }
            else
            {
                isThinking = false; 
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Parsing Error: " + e.Message);
            isThinking = false;
        }
    }

    private IEnumerator ExecutePlanRoutine(List<AgentActionData> plan)
    {
        int stepCounter = 1;
        foreach (var action in plan)
        {
            currentStepIndex = stepCounter++;
            headBubble?.ShowThought(action.thought_trace);
            
            agentState.IsActionExecuting = true;
            actionDispatcher.DispatchAction(action.function, action.args);
            
            float timeout = 30f; 
            float timer = 0f;

            while (agentState.IsActionExecuting && timer < timeout)
            {
                yield return null; 
                timer += Time.deltaTime;
            }

            if (timer >= timeout) 
            {
                agentState.IsActionExecuting = false;
                RecordActionTrace(action.function, "Unknown", false, "Action Timed Out");
            }
            yield return new WaitForSeconds(0.5f); 
        }
        
        headBubble?.ShowThought("Done!");
        isThinking = false; 
        currentStepIndex = 0;
    }

    private async void OnApplicationQuit()
    {
        if(websocket != null) await websocket.Close();
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
    [ContextMenu("Test: Simulate Server Command (Mock-Plate)")]
    public void TestMockTomatoServerResponse()
    {
        // 1. Set scene object names (Confirm objects with these names exist)
        string itemName = "PlateBoard";      // Item to take
        string tableName = "Preparation";

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
                    ""thought_trace"": ""1. Go to PlateBoard"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{itemName}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. Pickup Plate"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{itemName}"" }}
                }},
                {{
                    ""thought_trace"": ""3. Go to counter with Plate"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }},
                {{
                    ""thought_trace"": ""4. Put Plate on counter"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }}
            ]
        }}";

        // 4. Send command
        HandleServerResponse(mockJson);
    }
    [ContextMenu("Debug: Print Current State JSON")]
    public void DebugPrintCurrentState()
    {
        // 1. 使用現有的建構函式抓取資料
        AgentPayload payload = new AgentPayload();
        payload.self = BuildSelfData();
        payload.sensory = BuildSensoryData();

        // 2. 處理 Trace (為了測試，如果歷史是空的，我們塞一筆假的給你看)
        if (traceHistory.Count == 0)
        {
            Debug.Log("[Debug] 目前沒有動作紀錄，自動加入一筆測試資料...");
            ExecutionTraceItem mockTrace = new ExecutionTraceItem
            {
                step_index = 1,
                function = "test_function",
                target_id = "Debug_Target",
                status = "success",
                message = "This is a mock trace for debugging."
            };
            payload.execution_trace = new List<ExecutionTraceItem> { mockTrace };
        }
        else
        {
            // 正常的 Trace 邏輯
            if (traceHistory.Count > 5)
                payload.execution_trace = traceHistory.GetRange(traceHistory.Count - 5, 5);
            else
                payload.execution_trace = new List<ExecutionTraceItem>(traceHistory);
        }

        // 3. 序列化並列印
        string json = JsonConvert.SerializeObject(payload, Formatting.Indented);
        Debug.Log($"<color=cyan>[JSON Output]</color> Payload Size: {json.Length} chars\n{json}");
    }

    [ContextMenu("Debug: Print Full Mock JSON (Schema Check)")]
    public void DebugPrintFullMockState()
    {
        // 這是一個「完全假造」的資料，用來檢查 JSON 結構是否符合你的預期
        // 即使場景裡什麼都沒有，這個也會印出完美的格式
        
        AgentPayload mockPayload = new AgentPayload();

        // --- Self ---
        mockPayload.self = new SelfData
        {
            time_hour = 18,
            current_zone = "Kitchen_Zone",
            status = "Interacting",
            held_item = new HeldItemData
            {
                id = "Meatball_01",
                name = "Meatball",
                tags = new List<string> { "Raw", "Food" },
                temperature = "Cold"
            }
        };

        // --- Sensory ---
        mockPayload.sensory = new SensoryData
        {
            player_nearby = true,
            reachable_objects = new List<WorldObjectData>(),
            visible_objects = new List<WorldObjectData>()
        };

        // 假的可觸及物件 (Oven)
        var ovenData = new WorldObjectData
        {
            id = "Oven",
            type = "Station",
            distance = 1.2f,
            state = new Dictionary<string, object>()
        };
        ovenData.state["is_on"] = true;
        ovenData.state["cooking_progress"] = 0.5f;
        mockPayload.sensory.reachable_objects.Add(ovenData);

        // 假的遠處物件 (Plate)
        var plateData = new WorldObjectData
        {
            id = "Plate_1",
            type = "Plate",
            distance = 4.5f,
            state = new Dictionary<string, object>()
        };
        plateData.state["ready_to_serve"] = false;
        mockPayload.sensory.visible_objects.Add(plateData);

        // --- Trace ---
        mockPayload.execution_trace = new List<ExecutionTraceItem>
        {
            new ExecutionTraceItem { step_index = 1, function = "move_to", target_id = "MeatBox", status = "success", message = "Arrived" },
            new ExecutionTraceItem { step_index = 2, function = "pickup", target_id = "MeatBox", status = "success", message = "Got Meat" },
            new ExecutionTraceItem { step_index = 3, function = "move_to", target_id = "Oven", status = "failed", message = "Path Blocked" }
        };

        // 序列化
        string json = JsonConvert.SerializeObject(mockPayload, Formatting.Indented);
        Debug.Log($"<color=yellow>[Mock JSON Schema]</color>\n{json}");
    }
}

// =========================================================
//  資料結構 (符合你要求的 JSON 格式)
// =========================================================

[Serializable]
public class AgentPayload
{
    public SelfData self;
    public SensoryData sensory;
    public List<ExecutionTraceItem> execution_trace;
}

[Serializable]
public class SelfData
{
    public int time_hour;
    public string current_zone; 
    public string status;       
    public object held_item;
}

[Serializable]
public class HeldItemData
{
    public string id;
    public string name;
    public List<string> tags;   
    public string temperature;
}

[Serializable]
public class SensoryData
{
    public bool player_nearby;
    public List<WorldObjectData> reachable_objects; 
    public List<WorldObjectData> visible_objects;   
}

[Serializable]
public class WorldObjectData
{
    public string id;
    public string type;        
    public float distance;
    public Dictionary<string, object> state; // 使用 Dictionary 增加彈性
}

[Serializable]
public class ExecutionTraceItem
{
    public int step_index;
    public string function;
    public string target_id;
    public string status;   
    public string message; 
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
    public string function;
    public Dictionary<string, object> args;
}