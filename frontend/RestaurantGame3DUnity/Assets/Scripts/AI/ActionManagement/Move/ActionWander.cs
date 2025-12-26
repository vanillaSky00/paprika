using UnityEngine;
using UnityEngine.AI;
using System.Collections;
using System.Collections.Generic;

[RequireComponent(typeof(AgentMovement))]
[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(NavMeshAgent))]
public class ActionWander : MonoBehaviour, IAgentAction
{
    public string ActionName => "wander"; // Python 不需要呼叫這個，這是內部用的

    private AgentMovement agentMovement;
    private AgentState agentState;
    private NavMeshAgent navAgent;

    // 設定：亂走半徑與等待時間
    private float wanderRadius = 3.0f; 
    private float wanderTimeout = 10f;

    void Awake()
    {
        agentMovement = GetComponent<AgentMovement>();
        agentState = GetComponent<AgentState>();
        navAgent = GetComponent<NavMeshAgent>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 隨機找一個點
        Vector3 randomPoint = GetRandomNavMeshPoint(transform.position, wanderRadius);
        
        Debug.Log($"[ActionWander] 閒晃中... 目標: {randomPoint}");

        // 2. 開始移動 (這裡直接用協程，跟 ActionMove 很像)
        StartCoroutine(WaitUntilArrived(randomPoint));
    }

    // --- 隨機找點的數學魔法 ---
    private Vector3 GetRandomNavMeshPoint(Vector3 center, float range)
    {
        for (int i = 0; i < 10; i++) // 嘗試 10 次，避免運氣不好選到牆壁外
        {
            // 在球體範圍內隨機取點
            Vector3 randomPos = center + Random.insideUnitSphere * range;
            
            NavMeshHit hit;
            // 檢查這個點是否有 NavMesh 地板
            if (NavMesh.SamplePosition(randomPos, out hit, 1.0f, NavMesh.AllAreas))
            {
                return hit.position;
            }
        }
        // 如果真的衰到爆都找不到，就原地不動
        return center;
    }

    private IEnumerator WaitUntilArrived(Vector3 destination)
    {
        agentMovement.MoveTo(destination);
        yield return new WaitForSeconds(0.2f); // 等待路徑計算

        float timer = 0f;
        while (timer < wanderTimeout)
        {
            if (!navAgent.pathPending && (navAgent.remainingDistance <= navAgent.stoppingDistance))
            {
                if (!navAgent.hasPath || navAgent.velocity.sqrMagnitude == 0f) break;
            }
            timer += Time.deltaTime;
            yield return null;
        }

        agentMovement.Stop();
        
        // 這裡回報成功，讓 AI 知道「我閒晃完了，可以接下一個指令」
        // 或是你可以設計成「無限閒晃」，看你的需求
        agentState.ReportActionFinished(true, "Wander complete");
    }

    // --- 右鍵測試按鈕 ---
    [ContextMenu("測試：隨機走一步")]
    public void TestWanderOnce()
    {
        Execute(new Dictionary<string, object>());
    }
}