using UnityEngine;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(AgentNetworkManager))] // 🔥 建議加上這個，確保一定有 Manager
public class ActionCook : MonoBehaviour, IAgentAction
{
    public string ActionName => "cook";

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
        // --- 錯誤檢查 1: 參數不見了 ---
        if (!args.ContainsKey("id"))
        {
            string msg = "Missing 'id' argument";
            // 🔥 3. 寫入失敗紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Unknown", false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        string targetId = args["id"].ToString();
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);

        // --- 錯誤檢查 2: 找不到物件 ---
        if (targetObj == null)
        {
            string msg = $"Target '{targetId}' not found";
            // 🔥 寫入失敗紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        // --- 錯誤檢查 3: 距離太遠 ---
        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            string msg = $"Too far from {targetId}! Dist: {dist:F1}";
            // 🔥 寫入失敗紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        OvenBox ovenBox = targetObj.GetComponent<OvenBox>();
        if (ovenBox == null) ovenBox = targetObj.GetComponentInChildren<OvenBox>();

        // --- 錯誤檢查 4: 該物件不是烤箱 ---
        if (ovenBox == null)
        {
            string msg = "Target does not have OvenBox script!";
            // 🔥 寫入失敗紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        StartCoroutine(CookingRoutine(ovenBox, targetId));
    }

    private IEnumerator CookingRoutine(OvenBox ovenBox, string targetId)
    {
        agentState.IsActionExecuting = true;

        // 1. 面對爐子
        Vector3 lookPos = ovenBox.transform.position;
        lookPos.y = transform.position.y;
        transform.LookAt(lookPos);

        Debug.Log("[ActionCook] 開始等待食物煮熟...");

        float timeout = 20f; // 避免卡死
        float timer = 0f;

        // 2. 等待 OvenBox 變成可拿取狀態
        while (!ovenBox.canTake && timer < timeout)
        {
            timer += Time.deltaTime;
            yield return null; 
        }

        if (ovenBox.canTake)
        {
            Debug.Log("[ActionCook] 食物煮好了！任務結束 (請執行 Pickup)");
            
            string msg = "Food is cooked and ready on the stove.";
            // 🔥 4. 寫入成功紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, true, msg);

            agentState.ReportActionFinished(true, "Food is Ready");
        }
        else
        {
            string msg = "Cooking timed out (Oven state didn't change).";
            // 🔥 5. 寫入超時紀錄
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, "Cooking Timed out");
        }

        agentState.IsActionExecuting = false;
    }
}