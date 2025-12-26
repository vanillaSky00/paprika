using UnityEngine;
using UnityEngine.AI;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json;

[RequireComponent(typeof(AgentMovement))]
[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(NavMeshAgent))]
public class ActionMove : MonoBehaviour, IAgentAction
{
    public string ActionName => "move_to";

    private AgentMovement agentMovement;
    private AgentState agentState;
    private NavMeshAgent navAgent;
    private float moveTimeout = 15f; 

    void Awake()
    {
        agentMovement = GetComponent<AgentMovement>();
        agentState = GetComponent<AgentState>();
        navAgent = GetComponent<NavMeshAgent>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        Vector3 rawTargetPos = Vector3.zero;
        bool hasTarget = false;
        string targetName = "Unknown";

        // --- 模式 A: ID 自動感知 (這是你要的功能！) ---
        if (args.ContainsKey("id"))
        {
            string id = args["id"].ToString();
            //GameObject targetObj = GameObject.Find(id);
            GameObject targetObj = SmartObjectFinder.FindBestTarget(id, transform.position);

            if (targetObj != null)
            {
                Debug.Log($"[ActionMove] 智能鎖定目標: {id} -> {targetObj.name}");
                // 優先找有沒有設定 "InteractionPoint" (站位點)
                Transform standPoint = targetObj.transform.Find("InteractionPoint");
                
                if (standPoint != null)
                {
                    rawTargetPos = standPoint.position;
                    targetName = $"{id} (StandPoint)";
                    Debug.Log($"[ActionMove] 感知到物件 '{id}'，使用專屬站位點");
                }
                else
                {
                    rawTargetPos = targetObj.transform.position;
                    targetName = id;
                    Debug.Log($"[ActionMove] 感知到物件 '{id}'，使用中心點");
                }
                hasTarget = true;
            }
            else
            {
                Debug.LogError($"[ActionMove] 找不到物件 ID: {id}，請檢查場景物件名稱！");
                agentState.ReportActionFinished(false, $"Object '{id}' not found");
                return;
            }
        }
        // --- 模式 B: 純座標 (保留作為備用) ---
        else if (args.ContainsKey("target"))
        {
            try 
            {
                string json = JsonConvert.SerializeObject(args["target"]);
                float[] pos = JsonConvert.DeserializeObject<float[]>(json);
                if (pos != null && pos.Length >= 3)
                {
                    rawTargetPos = new Vector3(pos[0], pos[1], pos[2]);
                    hasTarget = true;
                }
            }
            catch { }
        }

        // --- 3. 執行移動邏輯 ---
        if (hasTarget)
        {
            // 自動校正：如果目標點在 Obstacle 內部 (不可走)，找最近的地板
            NavMeshHit hit;
            Vector3 finalTarget;

            // 搜尋半徑 2.0f
            if (NavMesh.SamplePosition(rawTargetPos, out hit, 2.0f, NavMesh.AllAreas))
            {
                finalTarget = hit.position;
            }
            else
            {
                finalTarget = rawTargetPos; // 真的找不到地板只好硬走
                Debug.LogWarning($"[ActionMove] 警告：{targetName} 附近找不到導航網格！");
            }

            // 啟動協程等待到達
            StartCoroutine(WaitUntilArrived(finalTarget));
        }
        else
        {
            agentState.ReportActionFinished(false, "Missing 'id' or 'target' argument");
        }
    }

    private IEnumerator WaitUntilArrived(Vector3 destination)
    {
        // 畫線除錯：紅色是路線
        Debug.DrawLine(transform.position, destination, Color.red, 2.0f);

        agentMovement.MoveTo(destination);
        
        // 重要：給 NavMeshAgent 一點時間計算路徑
        yield return new WaitForSeconds(0.2f); 

        float timer = 0f;
        bool hasArrived = false;

        while (timer < moveTimeout)
        {
            // 檢查是否到達
            if (!navAgent.pathPending && (navAgent.remainingDistance <= navAgent.stoppingDistance))
            {
                if (!navAgent.hasPath || navAgent.velocity.sqrMagnitude == 0f)
                {
                    hasArrived = true;
                    break;
                }
            }
            timer += Time.deltaTime;
            yield return null;
        }

        agentMovement.Stop();

        if (hasArrived)
            agentState.ReportActionFinished(true, $"Arrived at {destination}");
        else
            agentState.ReportActionFinished(false, "Move timeout or stuck");
    }
}