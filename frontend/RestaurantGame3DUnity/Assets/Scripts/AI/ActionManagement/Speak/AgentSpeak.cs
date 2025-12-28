using UnityEngine;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(AgentNetworkManager))]
public class AgentSpeak : MonoBehaviour, IAgentAction
{
    // 這對應到 LLM JSON 裡的 "function": "speak"
    public string ActionName => "speak"; 

    private AgentState agentState;
    private AgentNetworkManager networkManager;

    [Header("Settings")]
    [SerializeField] private float defaultDuration = 3.0f; // 預設講話顯示幾秒

    void Awake()
    {
        agentState = GetComponent<AgentState>();
        networkManager = GetComponent<AgentNetworkManager>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 解析內容
        string content = "";
        
        // 支援 "content" 或 "message" 兩種參數名稱
        if (args.ContainsKey("content")) content = args["content"].ToString();
        else if (args.ContainsKey("message")) content = args["message"].ToString();

        // 2. 檢查是否為空
        if (string.IsNullOrEmpty(content))
        {
            string error = "Speak content is empty";
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Self", false, error);
            agentState.ReportActionFinished(false, error);
            return;
        }

        // 3. 執行說話協程
        StartCoroutine(SpeakRoutine(content));
    }

    private IEnumerator SpeakRoutine(string content)
    {
        agentState.IsActionExecuting = true;

        // A. 顯示在頭頂氣泡 (使用你現有的 UI 整合)
        if (networkManager.headBubble != null)
        {
            // 如果你有專門的 "ShowDialogue"，可以用那個
            // 這裡暫時沿用 ShowThought，你可以加個前綴區分，例如 "🗣️ "
            networkManager.headBubble.ShowThought($"{content}"); 
        }
        
        Debug.Log($"[ActionSpeak] Agent 說: {content}");

        // B. 停留一段時間讓玩家閱讀 (根據字數動態調整，最少 2 秒)
        float waitTime = Mathf.Max(defaultDuration, content.Length * 0.1f);
        yield return new WaitForSeconds(waitTime);

        // C. 紀錄並結束
        string msg = $"Spoke: {content}";
        if (networkManager) networkManager.RecordActionTrace(ActionName, "Self", true, msg);
        
        // 這裡可以選擇不關閉氣泡，留給下一個動作覆蓋，或是清空
        // networkManager.headBubble.ShowThought(""); 

        agentState.ReportActionFinished(true, msg);
        agentState.IsActionExecuting = false;
    }
}