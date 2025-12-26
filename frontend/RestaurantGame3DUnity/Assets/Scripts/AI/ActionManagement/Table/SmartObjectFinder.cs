using UnityEngine;
using System.Linq; // 記得引用這個來做排序

public static class SmartObjectFinder
{
    // 傳入 "PrepTable"，回傳 "PrepTable_3" (最近且空的那個)
    public static GameObject FindBestTarget(string categoryId, Vector3 agentPos)
    {
        // 1. 先嘗試直接找 (如果 LLM 真的傳了 "PrepTable_1"，就直接用)
        GameObject directObj = GameObject.Find(categoryId);
        if (directObj != null) return directObj;

        // 2. 找不到完全符合的，就找所有名稱包含該字串的物件
        // (效能優化提示：如果物件很多，建議改用 Tag 搜尋)
        var candidates = GameObject.FindObjectsOfType<GameObject>()
            .Where(obj => obj.name.StartsWith(categoryId)) 
            .ToList();

        if (candidates.Count == 0) return null;

        Debug.Log($"[SmartFinder] 找到 {candidates.Count} 個 '{categoryId}' 類型的候選物件");

        // 3. 篩選與排序
        GameObject bestTarget = null;
        float closestDist = float.MaxValue;

        foreach (var obj in candidates)
        {
            // --- 檢查桌子是否已經有東西 (防呆) ---
            // 假設你的邏輯是：桌子上有東西就會被放到 InteractionPoint 底下
            // 或者用 Physics.CheckSphere 檢查桌面上方有沒有 Collider
            if (IsTableOccupied(obj.transform)) 
            {
                continue; // 這張桌子滿了，跳過
            }

            float d = Vector3.Distance(agentPos, obj.transform.position);
            if (d < closestDist)
            {
                closestDist = d;
                bestTarget = obj;
            }
        }

        return bestTarget;
    }

    // 檢查桌子是否被佔用
    private static bool IsTableOccupied(Transform table)
    {
        // 方法 A: 檢查是否有子物件 (如果你放東西是透過 SetParent)
        // 假設桌子有一個子物件叫 "InteractionPoint"，東西都放在那
        Transform point = table.Find("InteractionPoint");
        if (point != null && point.childCount > 0) return true;

        // 方法 B: 物理偵測 (更通用)
        // 在桌子上方 0.5 公尺處，畫一個半徑 0.3 的球，看有沒有撞到東西
        // 注意：要避開桌子本身的 Layer，不然會掃到自己
        Vector3 checkPos = table.position + Vector3.up * 0.5f; 
        Collider[] hits = Physics.OverlapSphere(checkPos, 0.3f);
        
        // 如果掃到任何不是 "Agent" 的東西，就當作被佔用
        foreach(var hit in hits)
        {
            if(hit.gameObject != table.gameObject && !hit.CompareTag("Player")) 
            {
                return true; 
            }
        }

        return false;
    }
}