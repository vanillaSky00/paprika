using System.Collections.Generic;
using UnityEngine;

public class AgentNearby : MonoBehaviour
{
    [Header("Config")]
    public float visionRadius = 5.0f;
    public Transform playerTransform; // 記得在 Inspector 拉入玩家
    public string targetTag = "Interactable";

    [Header("References")]
    public Transform agentEyeTransform; // 也可以直接用 transform

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

                objects.Add(new WorldObjectData
                {
                    id = hit.name,
                    type = "Prop", 
                    distance = Vector3.Distance(transform.position, hit.transform.position),
                    state = defaultState // <--- 這裡現在傳入的是 Dictionary，不再是 string
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