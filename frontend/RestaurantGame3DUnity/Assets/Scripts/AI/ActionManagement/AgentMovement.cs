using UnityEngine;
using UnityEngine.AI;

// 這腳本負責操作 NavMeshAgent (硬體層)
[RequireComponent(typeof(NavMeshAgent))]
[RequireComponent(typeof(Animator))]
public class AgentMovement : MonoBehaviour
{
    private NavMeshAgent agent;
    private Animator anim;

    void Awake()
    {
        agent = GetComponent<NavMeshAgent>();
        anim = GetComponent<Animator>();
    }

    public void MoveTo(Vector3 targetPosition)
    {
        // 1. 設定導航目標
        agent.SetDestination(targetPosition);
        agent.isStopped = false;
    }

    public void Stop()
    {
        agent.isStopped = true;
    }

    void Update()
    {
        // --- 判斷是否正在移動的 3 個條件 ---
        // 1. pathPending: 是否還在計算路徑 (如果是，代表還沒開始走，不算移動)
        // 2. remainingDistance: 剩餘距離是否大於停止距離 (例如 0.1)
        // 3. velocity: 雖然有路徑，但如果被卡住速度為 0，也不算在走 (選用)

        if (!agent.pathPending)
        {
            if (agent.remainingDistance <= agent.stoppingDistance)
            {
                // 到達終點了 -> 停止走路
                if (!agent.hasPath || agent.velocity.sqrMagnitude == 0f)
                {
                    SetWalking(false);
                }
            }
            else
            {
                // 還沒到 -> 繼續走
                SetWalking(true);
            }
        }
    }
    private void SetWalking(bool isWalking)
    {
        if (anim != null)
        {
            anim.SetBool("isMoving", isWalking);
        }
    }
}