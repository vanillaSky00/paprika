using UnityEngine;
using System.Linq;

public static class SmartObjectFinder
{
    /// <summary>
    /// 尋找最近且未被佔用的目標物件 (支援模糊搜尋與佔用檢查)
    /// </summary>
    /// <param name="categoryId">物件名稱或類別前綴 (如 "PrepTable")</param>
    /// <param name="agentPos">Agent 當前位置</param>
    /// <returns>最佳目標物件，如果全滿則回傳 null</returns>
    public static GameObject FindBestTarget(string categoryId, Vector3 agentPos)
    {
        // 1. 先嘗試直接找 (如果指令指名道姓要去 "PrepTable_1")
        GameObject directObj = GameObject.Find(categoryId);
        if (directObj != null) 
        {
            // 如果指名的桌子滿了，我們還是回傳它嗎？
            // 通常指名道姓代表強制，但如果你希望它自動換桌，可以把下面這行打開：
            // if (IsTableOccupied(directObj.transform)) { /* 繼續往下找備案 */ }
            return directObj;
        }

        // 2. 模糊搜尋：找出所有名稱以 categoryId 開頭的物件
        var candidates = GameObject.FindObjectsOfType<GameObject>()
            .Where(obj => obj.name.StartsWith(categoryId)) 
            .OrderBy(obj => Vector3.Distance(agentPos, obj.transform.position)) // 先按距離排序 (最近的優先)
            .ToList();

        if (candidates.Count == 0) 
        {
            Debug.LogWarning($"[SmartFinder] 找不到任何名稱以 '{categoryId}' 開頭的物件");
            return null;
        }

        Debug.Log($"[SmartFinder] 🔍 開始掃描 {candidates.Count} 個 '{categoryId}' 候選物件...");

        foreach (var obj in candidates)
        {
            float dist = Vector3.Distance(agentPos, obj.transform.position);

            // 檢查是否被佔用
            if (IsTableOccupied(obj.transform)) 
            {
                Debug.Log($"❌ [跳過] {obj.name} (距離: {dist:F1}m) -> 判定為【已佔用】");
                continue; // 這張滿了，找下一張
            }

            // 找到第一個「最近」且「空」的，直接回傳
            Debug.Log($"✅ [鎖定] {obj.name} (距離: {dist:F1}m) -> 判定為【空閒】");
            return obj;
        }

        Debug.LogWarning($"⚠️ [SmartFinder] 所有 '{categoryId}' 類型的桌子都滿了！");
        return null;
    }

    /// <summary>
    /// 檢查桌子是否被佔用 (支援 ItemHolder 結構與物理偵測)
    /// </summary>
    private static bool IsTableOccupied(Transform table)
    {
        // --- 策略 A: ItemHolder 結構檢查 (最準確，針對你的截圖) ---
        Transform itemHolder = table.Find("ItemHolder");
        if (itemHolder != null)
        {
            // 遍歷 ItemHolder 底下所有預設食材 (Meatball, Tomato...)
            foreach(Transform child in itemHolder)
            {
                // 只要有任何一個子物件是 "Active" (開啟的)，就代表桌上有東西
                if (child.gameObject.activeSelf) 
                {
                    // Debug.Log($"[SmartFinder] {table.name} 滿了 (發現開啟的 {child.name})");
                    return true; 
                }
            }
            
            // 如果找到了 ItemHolder，但裡面所有食材都是關閉的 (inactive)，那就是空的
            return false; 
        }

        // --- 策略 B: InteractionPoint 結構檢查 (相容舊版結構) ---
        Transform point = table.Find("InteractionPoint");
        if (point != null)
        {
            // 如果是用 Instantiate 生成子物件的方式，檢查 childCount
            if (point.childCount > 0) return true;
        }

        // --- 策略 C: 物理射線偵測 (最後防線) ---
        // 當上述兩種結構都找不到時，用物理碰撞檢查
        Vector3 checkPos = table.position + Vector3.up * 0.6f; // 偵測高度 (請依桌子高度調整)
        float radius = 0.4f; // 偵測半徑

        // 畫出除錯線 (Scene 視窗可見紅色十字)
        Debug.DrawLine(checkPos - Vector3.right * radius, checkPos + Vector3.right * radius, Color.red, 1.0f);
        Debug.DrawLine(checkPos - Vector3.forward * radius, checkPos + Vector3.forward * radius, Color.red, 1.0f);

        Collider[] hits = Physics.OverlapSphere(checkPos, radius);
        
        foreach(var hit in hits)
        {
            GameObject hitObj = hit.gameObject;

            // 排除清單：
            // 1. 桌子自己
            // 2. 桌子的子物件 (如果是模型的一部分)
            // 3. 玩家 (Player) 或 Agent
            if (hitObj != table.gameObject && 
                !hit.transform.IsChildOf(table) &&
                !hitObj.CompareTag("Player") && 
                !hitObj.CompareTag("Agent")) 
            {
                Debug.Log($"❗ {table.name} 被物理偵測判定佔用 (撞到: {hitObj.name})");
                return true; 
            }
        }

        return false;
    }
}