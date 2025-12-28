using UnityEngine;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(AgentNetworkManager))] // 🔥 確保有 Manager
public class ActionChop : MonoBehaviour, IAgentAction
{
    // 如果你之前改成了 "cut"，這裡記得要對應改成 "cut"，否則 LLM 會找不到
    public string ActionName => "chop"; 

    private AgentState agentState;
    private AgentNetworkManager networkManager; // 🔥 1. 新增變數
    
    [SerializeField] private float interactDistance = 2.5f; 

    void Awake()
    {
        agentState = GetComponent<AgentState>();
        networkManager = GetComponent<AgentNetworkManager>(); // 🔥 2. 抓取元件
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 檢查參數
        if (!args.ContainsKey("id"))
        {
            string msg = "Missing 'id'";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Unknown", false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        string targetId = args["id"].ToString();
        
        // 2. 找到目標
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);

        if (targetObj == null)
        {
            string msg = $"Target '{targetId}' not found";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            string msg = $"Too far from target! Distance: {dist:F1}m > Limit: {interactDistance}m";
            Debug.LogWarning($"[ActionChop] {msg}");
            
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 3. 檢查是否有 SliceBoard 腳本
        SliceBoard board = targetObj.GetComponent<SliceBoard>();
        if (board == null)
        {
            board = targetObj.GetComponentInChildren<SliceBoard>();
        }

        if (board == null)
        {
            string msg = $"Target {targetId} does not have SliceBoard script!";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 4. 開始切菜 (🔥 把 targetId 傳進去，方便紀錄)
        StartCoroutine(ProcessRoutine(board, targetId));
    }

    private IEnumerator ProcessRoutine(SliceBoard board, string targetId)
    {
        agentState.IsActionExecuting = true;

        // 面對桌子
        Vector3 lookPos = board.transform.position;
        lookPos.y = transform.position.y;
        transform.LookAt(lookPos);

        Debug.Log($"[ActionChop] 開始加工 {board.name}...");

        ItemType resultItem = ItemType.NONE;
        float safetyTimer = 0f;
        
        // 模擬按住按鍵，持續呼叫 Process
        while (resultItem == ItemType.NONE && safetyTimer < 10f)
        {
            resultItem = board.Process();
            safetyTimer += Time.deltaTime;
            yield return null; 
        }

        if (resultItem != ItemType.NONE)
        {
            string msg = $"Chopped into {resultItem}";
            Debug.Log($"[ActionChop] 加工完成！獲得: {resultItem}");

            // 更新桌上的視覺模型
            board.ClearObject();      
            board.PutItem(resultItem); 

            // 🔥 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, true, msg);

            agentState.ReportActionFinished(true, msg);
        }
        else
        {
            string msg = "Process failed or timed out";
            Debug.LogWarning("[ActionChop] " + msg);
            
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
        }

        agentState.IsActionExecuting = false;
    }
}