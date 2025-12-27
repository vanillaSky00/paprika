using UnityEngine;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
public class ActionChop : MonoBehaviour, IAgentAction
{
    public string ActionName => "chop";

    private AgentState agentState;
    
    [SerializeField] private float interactDistance = 2.5f; 

    void Awake()
    {
        agentState = GetComponent<AgentState>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 檢查參數
        if (!args.ContainsKey("id"))
        {
            agentState.ReportActionFinished(false, "Missing 'id'");
            return;
        }

        string targetId = args["id"].ToString();
        
        // 2. 找到目標
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);

        if (targetObj == null)
        {
            agentState.ReportActionFinished(false, $"Target '{targetId}' not found");
            return;
        }

        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            string errorMsg = $"Too far from target! Distance: {dist:F1}m > Limit: {interactDistance}m";
            Debug.LogWarning($"[ActionChop] {errorMsg}");
            agentState.ReportActionFinished(false, errorMsg);
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
            agentState.ReportActionFinished(false, $"Target {targetId} does not have SliceBoard script!");
            return;
        }

        // 4. 開始切菜
        StartCoroutine(ProcessRoutine(board));
    }

    private IEnumerator ProcessRoutine(SliceBoard board)
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
            Debug.Log($"[ActionChop] 加工完成！獲得: {resultItem}");

            // 更新桌上的視覺模型
            board.ClearObject();      
            board.PutItem(resultItem); 

            agentState.ReportActionFinished(true, $"Chopped into {resultItem}");
        }
        else
        {
            Debug.LogWarning("[ActionChop] 加工失敗或超時");
            agentState.ReportActionFinished(false, "Process failed or timed out");
        }

        agentState.IsActionExecuting = false;
    }
}