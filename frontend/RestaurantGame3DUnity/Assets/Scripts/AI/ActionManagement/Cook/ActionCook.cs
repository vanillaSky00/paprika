using UnityEngine;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
public class ActionCook : MonoBehaviour, IAgentAction
{
    public string ActionName => "cook";

    private AgentState agentState;
    [SerializeField] private float interactDistance = 2.5f;

    void Awake()
    {
        agentState = GetComponent<AgentState>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        if (!args.ContainsKey("id"))
        {
            agentState.ReportActionFinished(false, "Missing 'id'");
            return;
        }

        string targetId = args["id"].ToString();
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);

        if (targetObj == null)
        {
            agentState.ReportActionFinished(false, $"Target '{targetId}' not found");
            return;
        }

        // 距離檢查
        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            agentState.ReportActionFinished(false, $"Too far from Oven! Dist: {dist:F1}");
            return;
        }

        OvenBox ovenBox = targetObj.GetComponent<OvenBox>();
        if (ovenBox == null) ovenBox = targetObj.GetComponentInChildren<OvenBox>();

        if (ovenBox == null)
        {
            agentState.ReportActionFinished(false, "Target does not have OvenBox script!");
            return;
        }

        StartCoroutine(CookingRoutine(ovenBox));
    }

    private IEnumerator CookingRoutine(OvenBox ovenBox)
    {
        agentState.IsActionExecuting = true;

        // 1. 面對爐子
        Vector3 lookPos = ovenBox.transform.position;
        lookPos.y = transform.position.y;
        transform.LookAt(lookPos);

        Debug.Log("[ActionCook] 開始等待食物煮熟...");

        float timeout = 20f; // 避免卡死
        float timer = 0f;

        // 2. 什麼都不做，就是等待 OvenBox 變成可拿取狀態
        // (Oven.cs 會自己在背景跑計時器，跑完會把 ovenBox.canTake 設為 true)
        while (!ovenBox.canTake && timer < timeout)
        {
            timer += Time.deltaTime;
            yield return null; 
        }

        if (ovenBox.canTake)
        {
            Debug.Log("[ActionCook] 食物煮好了！任務結束 (請執行 Pickup)");
            agentState.ReportActionFinished(true, "Food is Ready");
        }
        else
        {
            agentState.ReportActionFinished(false, "Cooking Timed out");
        }

        agentState.IsActionExecuting = false;
    }
}