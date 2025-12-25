using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;
using NativeWebSocket; // 需安裝 NativeWebSocket 套件

public class AgentNetworkManager : MonoBehaviour
{
    [Header("Components")]
    public AgentState agentState;          // 需在 Inspector 綁定
    public AgentNearby agentNearby; // 需在 Inspector 綁定

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
        string uuid = System.Guid.NewGuid().ToString();
        string fullUrl = serverUrl + uuid;

        Debug.Log($"Generated Client ID: {uuid}");
        Debug.Log($"Connecting to: {fullUrl}");

        websocket = new WebSocket(fullUrl);

        websocket.OnOpen += () => Debug.Log("Connection open!");
        
        websocket.OnError += (e) => Debug.LogError("Error: " + e);
        
        websocket.OnClose += (e) => Debug.Log("Connection closed!");

        websocket.OnMessage += (bytes) =>
        {
            // 收到 Server 回傳的 Plan
            string message = System.Text.Encoding.UTF8.GetString(bytes);
            HandleServerResponse(message);
        };

        // 啟動連線
        await websocket.Connect();
        
        // 開始發送 Perception 的循環 (例如每 2 秒或是動作執行完後)
        StartCoroutine(AgentLoopRoutine());
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
        isThinking = false; // 解鎖，允許下一次傳送

        try
        {
            ServerResponse response = JsonConvert.DeserializeObject<ServerResponse>(json);
            
            // TODO: 把這些動作傳給你的 ActionController 去執行
            foreach (var action in response.plan)
            {
                Debug.Log($"Next Action: {action.function} on {JsonConvert.SerializeObject(action.args)}");
                // StartCoroutine(actionController.Execute(action));
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Parsing Error: " + e.Message);
        }
    }

    private async void OnApplicationQuit()
    {
        if(websocket != null) await websocket.Close();
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
    public string current_task;
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