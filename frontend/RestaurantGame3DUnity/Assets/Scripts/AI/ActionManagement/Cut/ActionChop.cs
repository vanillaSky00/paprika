using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.Linq;

[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(AgentNetworkManager))] 
[RequireComponent(typeof(Inventory))] // 🔥 1. 確保有 Inventory，才能把東西拿起來
public class ActionChop : MonoBehaviour, IAgentAction
{
    public string ActionName => "chop"; 

    private AgentState agentState;
    private AgentNetworkManager networkManager;
    private Inventory inventory; // 🔥 2. 新增 Inventory 變數
    
    [SerializeField] private float interactDistance = 2.5f; 

    void Awake()
    {
        agentState = GetComponent<AgentState>();
        networkManager = GetComponent<AgentNetworkManager>();
        inventory = GetComponent<Inventory>(); // 🔥 3. 抓取 Inventory 元件
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 檢查參數
        if (!args.ContainsKey("id"))
        {
            string msg = "Missing 'id'";
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Unknown", false, msg);
            agentState.ReportActionFinished(false, msg);
            return;
        }

        string rawId = args["id"].ToString();
        string targetId = ResolveTargetId(rawId);
        
        // 2. 找到目標
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);

        if (targetObj == null)
        {
            string msg = $"Target '{targetId}' not found";
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
            agentState.ReportActionFinished(false, msg);
            return;
        }

        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            string msg = $"Too far from target! Distance: {dist:F1}m > Limit: {interactDistance}m";
            Debug.LogWarning($"[ActionChop] {msg}");
            
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
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 4. 開始切菜
        StartCoroutine(ProcessRoutine(board, targetId));
    }

    private string ResolveTargetId(string inputId)
    {
        string cleanId = inputId.Trim().ToLower();
        Dictionary<string, string> aliasMap = new Dictionary<string, string>()
        {
            { "onion",   "CutBoard" },
            { "tomato",  "CutBoard" },
            { "lettuce", "CutBoard" },
            { "cheese",  "CutBoard" },
            { "chese",   "CutBoard" },
            { "bread",   "CutBoard" }
        };

        if (aliasMap.ContainsKey(cleanId))
        {
            return aliasMap[cleanId];
        }
        return inputId;
    }

    private IEnumerator ProcessRoutine(SliceBoard board, string targetId)
    {
        agentState.IsActionExecuting = true;

        Vector3 lookPos = board.transform.position;
        lookPos.y = transform.position.y;
        transform.LookAt(lookPos);

        Debug.Log($"[ActionChop] 開始加工 {board.name}...");

        ItemType resultItem = ItemType.NONE;
        float safetyTimer = 0f;
        
        while (resultItem == ItemType.NONE && safetyTimer < 10f)
        {
            resultItem = board.Process();
            safetyTimer += Time.deltaTime;
            yield return null; 
        }

        if (resultItem != ItemType.NONE)
        {
            // 🔥 4. 修改這裡：切完直接拿起來，而不是放回桌上
            string msg = $"Chopped into {resultItem} and auto-picked up";
            Debug.Log($"[ActionChop] 加工完成！自動撿起: {resultItem}");

            // A. 清空桌子 (因為東西被變出來了)
            board.ClearObject(); 
            
            // B. 直接放進手上 (Inventory)
            inventory.TakeItem(resultItem);

            // C. 告訴 Agent State 現在手上有東西 (重要！否則 LLM 下一輪會以為手是空的)
            agentState.SetHeldItem(resultItem.ToString());

            // 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, true, msg);

            agentState.ReportActionFinished(true, msg);
        }
        else
        {
            string msg = "Process failed or timed out";
            Debug.LogWarning("[ActionChop] " + msg);
            
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

            agentState.ReportActionFinished(false, msg);
        }

        agentState.IsActionExecuting = false;
    }
}