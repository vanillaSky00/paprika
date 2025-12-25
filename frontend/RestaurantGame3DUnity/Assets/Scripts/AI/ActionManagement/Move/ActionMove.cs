using UnityEngine;
using System.Collections.Generic;
using Newtonsoft.Json; // 你的專案有裝這個對吧？

[RequireComponent(typeof(AgentMovement))]
[RequireComponent(typeof(AgentState))]
public class ActionMove : MonoBehaviour, IAgentAction
{
    // 對應 Python 傳來的 function 名稱
    public string ActionName => "move_to";

    private AgentMovement agentMovement;
    private AgentState agentState;

    void Awake()
    {
        agentMovement = GetComponent<AgentMovement>();
        agentState = GetComponent<AgentState>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        Vector3 targetPos = Vector3.zero;
        bool hasTarget = false;

        // --- 解析座標 (支援兩種格式) ---

        // 格式 A: "target": [10, 0, 5] (最常見)
        if (args.ContainsKey("target"))
        {
            try 
            {
                // 把 object 轉回 Json string 再轉 float[]，這是處理弱型別最穩的方法
                string json = JsonConvert.SerializeObject(args["target"]);
                float[] pos = JsonConvert.DeserializeObject<float[]>(json);
                if (pos != null && pos.Length >= 3)
                {
                    targetPos = new Vector3(pos[0], pos[1], pos[2]);
                    hasTarget = true;
                }
            }
            catch { Debug.LogError("[ActionMove] 座標解析失敗"); }
        }
        // 格式 B: "x": 10, "z": 5 (有時候 LLM 會這樣給)
        else if (args.ContainsKey("x") && args.ContainsKey("z"))
        {
            float x = System.Convert.ToSingle(args["x"]);
            float z = System.Convert.ToSingle(args["z"]);
            float y = args.ContainsKey("y") ? System.Convert.ToSingle(args["y"]) : 0;
            targetPos = new Vector3(x, y, z);
            hasTarget = true;
        }

        // --- 執行移動 ---
        if (hasTarget)
        {
            Debug.Log($"[ActionMove] 前往座標: {targetPos}");
            agentMovement.MoveTo(targetPos);
            
            // 回報狀態
            agentState.ReportActionFinished(true, $"Moving to {targetPos}");
        }
        else
        {
            Debug.LogError("[ActionMove] 缺少座標參數 (target 或 x,z)");
            agentState.ReportActionFinished(false, "Missing coordinates");
        }
    }

    // --- 右鍵測試 ---
    [ContextMenu("測試：走到 (-5, 0.51, 3.0)")]
    public void TestMoveZero()
    {
        // 模擬 Python 傳來的參數
        var args = new Dictionary<string, object> { 
            { "target", new float[] { -5.0f, 0.51f, 3.0f } } 
        };
        Execute(args);
    }
}