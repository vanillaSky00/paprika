using UnityEngine;

public class RoomTrigger : MonoBehaviour
{
    public string roomName = "Kitchen"; // 在 Inspector 設定每個房間的名字

    private void OnTriggerEnter(Collider other)
    {
        // 假設 Agent 身上掛有 AgentState
        AgentState agent = other.GetComponent<AgentState>();
        if (agent != null)
        {
            agent.SetLocation(roomName);
            Debug.Log($"Agent entered: {roomName}");
        }
    }
}