using System.Collections.Generic;
using UnityEngine;

public class AgentPerception : MonoBehaviour
{
    [Header("Config")]
    public float visionRadius = 5.0f;
    public Transform playerTransform; // 記得在 Inspector 拉入玩家

    [Header("References")]
    public Transform agentEyeTransform; // 也可以直接用 transform

    public bool CheckPlayerNearby()
    {
        if (playerTransform == null) return false;
        
        float dist = Vector3.Distance(transform.position, playerTransform.position);
        return dist <= visionRadius;
    }

    public List<WorldObjectData> ScanNearbyObjects()
    {
        List<WorldObjectData> objects = new List<WorldObjectData>();
        
        // 這裡放原本的 Physics.OverlapSphere 邏輯
        Collider[] hits = Physics.OverlapSphere(transform.position, visionRadius);
        foreach(var hit in hits)
        {
            if(hit.CompareTag("Interactable"))
            {
                objects.Add(new WorldObjectData
                {
                    id = hit.name,
                    type = "Prop", // 可根據 Tag 或 Component 進一步細分
                    position = new PositionData { 
                        x = hit.transform.position.x, 
                        y = hit.transform.position.y, 
                        z = hit.transform.position.z 
                    },
                    distance = Vector3.Distance(transform.position, hit.transform.position),
                    state = "default"
                });
            }
        }
        return objects;
    }
    
    // 視覺化偵測範圍 (Debug 用)
    private void OnDrawGizmosSelected()
    {
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(transform.position, visionRadius);
    }
}