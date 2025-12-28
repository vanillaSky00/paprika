using System.Collections.Generic;
using UnityEngine;

public class AgentNearby : MonoBehaviour
{
    [Header("Config")]
    public float visionRadius = 5.0f;
    public Transform playerTransform;
    public string targetTag = "Interactable";

    [Header("References")]
    public Transform agentEyeTransform;

    public bool CheckPlayerNearby()
    {
        if (playerTransform == null) return false;
        
        float dist = Vector3.Distance(transform.position, playerTransform.position);
        return dist <= visionRadius;
    }

    // 這個函式是用來掃描周圍物件的
    public List<WorldObjectData> ScanNearbyObjects()
    {
        List<WorldObjectData> objects = new List<WorldObjectData>();
        
        Collider[] hits = Physics.OverlapSphere(transform.position, visionRadius);
        foreach(var hit in hits)
        {
            if(hit.CompareTag(targetTag)) {
                
                // 🔥 修復點：建立一個 Dictionary 來符合新的資料結構
                Dictionary<string, object> defaultState = new Dictionary<string, object>();
                defaultState["info"] = "default_prop";

                Vector3 closestPoint = hit.ClosestPoint(transform.position);
                float realDistance = Vector3.Distance(transform.position, closestPoint);

                objects.Add(new WorldObjectData
                {
                    id = hit.name,
                    type = "Prop", 
                    distance = realDistance,
                    state = defaultState
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