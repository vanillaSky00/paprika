using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;
using NativeWebSocket; // 需安裝 NativeWebSocket 套件

public class AgentNetworkManager : MonoBehaviour
{
    [Header("Components")]
    public AgentState agentState;           // 需在 Inspector 綁定
    public AgentNearby agentNearby;         // 需在 Inspector 綁定

    [Header("Actions")]
    public ActionDispatcher actionDispatcher;   // 需在 Inspector 綁定

    [Header("Connection Config")]
    // public string serverUrl = "ws://localhost:8000/api/ws/agent/player_1";
    public string serverUrl = "ws://localhost:8000/api/ws/agent/";
    public bool autoReconnect = true;

    [Header("Game State References")]
    public Transform agentTransform;
    // 這裡建議放一個負責執行動作的腳本參考，例如:
    // public ActionController actionController; 

    private WebSocket websocket;
    private bool isThinking = false; // 避免在 AI 還在思考時重複發送請求

    async void Start()
    {
        try
        {
            string uuid = System.Guid.NewGuid().ToString();
            string fullUrl = $"ws://127.0.0.1:8000/api/ws/agent/{uuid}";

            Debug.Log($"[AI] Initializing connection to: {fullUrl}");
            websocket = new WebSocket(fullUrl);

            websocket.OnOpen += () => {
                Debug.Log("<color=green>[AI] Connection Verified by Unity!</color>");
                StartCoroutine(AgentLoopRoutine());
            };

            websocket.OnError += (e) => Debug.LogError($"[AI] Connection Error: {e}");
            websocket.OnClose += (c) => Debug.LogWarning($"[AI] Connection Closed. Code: {c}");

            websocket.OnMessage += (bytes) =>
            {
                // 收到 Server 回傳的 Plan
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
        if (Time.frameCount % 60 == 0 && websocket != null)
        {
            Debug.Log($"[AI] Current Live State: {websocket.State}");
        }
    }

    private IEnumerator AgentLoopRoutine()
    {
        while (true)
        {
            Debug.Log($"websocket.State: {websocket.State}");
            Debug.Log($"isThinking: {isThinking}");
            // 只有在連線開啟且沒有在思考時才傳送
            if (websocket.State == WebSocketState.Open && !isThinking)
            {
                SendPerception();
            }
            // maybe dynamic freqency, for different work
            yield return new WaitForSeconds(1.0f); // 調整頻率
        }
    }

    async void SendPerception()
    {
        isThinking = true;

        agentState.GetLastActionStatus(out string status, out string error);
        // 1. 收集場景資訊 (這裡要對應 Python 的 Perception Schema)
        var perception = new PerceptionData
        {
            time_hour = System.DateTime.Now.Hour, // 或遊戲內時間
            day = 1, // 遊戲天數
            mode = "reality",
            location_id = agentState.GetLocationId(),

            player_nearby = agentNearby.CheckPlayerNearby(),
            nearby_objects = agentNearby.ScanNearbyObjects(),
            held_item = agentState.GetHeldItem(),
            
            // 重要：回報上一個動作的執行結果
            last_action_status = status,
            last_action_error = error
        };
        //Debug.Log($"[準備傳送] 地點: {perception.location_id}");
        string json = JsonConvert.SerializeObject(perception);
        await websocket.SendText(json);
    }

    private List<WorldObjectData> ScanNearbyObjects()
    {
        // 範例：搜尋半徑內的物件
        List<WorldObjectData> objects = new List<WorldObjectData>();
        
        // 假設所有互動式物件都有 "Interactable" Tag
        // 這邊只是範例，實際請根據你的遊戲邏輯撰寫
        Collider[] hits = Physics.OverlapSphere(agentTransform.position, 5.0f);
        foreach(var hit in hits)
        {
            if(hit.CompareTag("Interactable"))
            {
                objects.Add(new WorldObjectData
                {
                    id = hit.name, // 例如 "Stove_01"
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
                Debug.Log($"[Agent] 收到任務: {response.task}，共 {response.plan.Count} 個步驟");
                // 改成啟動協程，一步一步執行
                StartCoroutine(ExecutePlanRoutine(response.plan));
            }
            else
            {
                Debug.Log("[Agent] 收到回應但沒有計畫 (閒聊或思考中)");
                isThinking = false; // 沒事做，直接解鎖思考
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Parsing Error: " + e.Message);
            isThinking = false; // 出錯也要解鎖
        }
    }
    private IEnumerator ExecutePlanRoutine(List<AgentActionData> plan)
    {
        foreach (var action in plan)
        {
            Debug.Log($"[Agent] is running: {action.function} ({action.thought_trace})");
            
            // 1. 執行動作
            actionDispatcher.DispatchAction(action.function, action.args);
            
            // 2. 等待動作完成
            // 簡單做法：每個動作給它 3 秒鐘 (移動可能需要比較久)
            // 進階做法：以後可以改寫成等待 Action 回傳 callback
            yield return new WaitForSeconds(3.0f); 
        }

        Debug.Log("[Agent] Task Finished！");
        
        // 全部做完後，才允許 AI 再次看環境思考
        isThinking = false; 
        
        // 可以選擇做完馬上再看一次環境
        // SendPerception(); 
    }
    private async void OnApplicationQuit()
    {
        if(websocket != null) await websocket.Close();
    }
    private void OnDestroy()
    {
        StopAllCoroutines();
    }

    [ContextMenu("測試：模擬 Server 指令 (Mock-Onion ID版)")]
    public void TestMockServerResponse_NoNumbers()
    {
        // 1. 設定場景物件名稱
        string itemName = "OnionBox";       // 要拿的
        string tableName = "Plate_agent_2"; // 要放的

        // 2. 防呆檢查 (只是為了確保場景沒壞，不需要取座標了)
        if (GameObject.Find(itemName) == null || GameObject.Find(tableName) == null)
        {
            Debug.LogError($"[Test Error] 找不到物件！請確認場景裡有 '{itemName}' 和 '{tableName}'");
            return;
        }

        Debug.Log($"[Test] 啟動純 ID 導航測試: {itemName} -> {tableName}");

        // 3. 捏造 JSON 指令 (完全不含座標數字)
        // 注意看 move_to 的參數，現在只傳 "id"
        string mockJson = $@"
        {{
            ""task"": ""運送洋蔥 (ID 導航版)"",
            ""plan"": [
                {{
                    ""thought_trace"": ""1. 前往洋蔥箱"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{itemName}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. 撿起洋蔥"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{itemName}"" }}
                }},
                {{
                    ""thought_trace"": ""3. 拿著洋蔥前往櫃檯"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }},
                {{
                    ""thought_trace"": ""4. 把洋蔥放在櫃檯上"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }}
            ]
        }}";

        // 4. 發送指令
        HandleServerResponse(mockJson);
    }
    [ContextMenu("測試：模擬 Server 指令 (Mock-Tomato ID版)")]
    public void TestMockTomatoServerResponse()
    {
        // 1. 設定場景物件名稱 (請確認場景裡真的有這些名字的物件)
        string itemName = "TomatoBox";      // 要拿的東西
        string tableName = "Plate_agent_1"; // 要放的桌子

        // 2. 防呆檢查 (確保場景有這東西，不然 ActionMove 也會找不到)
        if (GameObject.Find(itemName) == null || GameObject.Find(tableName) == null)
        {
            Debug.LogError($"[Test Error] 找不到物件！請確認場景裡有 '{itemName}' 和 '{tableName}'");
            return;
        }

        Debug.Log($"[Test] 啟動番茄搬運測試 (ID模式): {itemName} -> {tableName}");

        // 3. 捏造 JSON 指令 (完全不含座標數字)
        // 注意：這裡 move_to 的 args 改成用 "id"
        string mockJson = $@"
        {{
            ""task"": ""運送蕃茄到櫃檯 (測試)"",
            ""plan"": [
                {{
                    ""thought_trace"": ""1. 前往番茄箱"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{itemName}"" }} 
                }},
                {{
                    ""thought_trace"": ""2. 撿起番茄"",
                    ""function"": ""pickup"",
                    ""args"": {{ ""id"": ""{itemName}"" }}
                }},
                {{
                    ""thought_trace"": ""3. 拿著番茄前往櫃檯"",
                    ""function"": ""move_to"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }},
                {{
                    ""thought_trace"": ""4. 把番茄放在櫃檯上"",
                    ""function"": ""put_down"",
                    ""args"": {{ ""id"": ""{tableName}"" }}
                }}
            ]
        }}";

        // 4. 發送指令
        HandleServerResponse(mockJson);
    }
}

// --- Data Classes (DTOs) 對應 Python Schemas ---

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