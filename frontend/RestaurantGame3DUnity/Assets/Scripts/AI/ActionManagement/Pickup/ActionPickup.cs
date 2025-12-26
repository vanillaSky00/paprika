using UnityEngine;
using System.Collections.Generic;

// 必須依賴 Inventory 和 AgentState
[RequireComponent(typeof(Inventory))]
[RequireComponent(typeof(AgentState))]
public class ActionPickup : MonoBehaviour, IAgentAction
{
    // 對應 Server 傳來的 function 名稱
    public string ActionName => "pickup";

    private Inventory inventory;
    private AgentState agentState;
    
    // 設定最大互動距離 (例如 2.5 公尺)
    [SerializeField] private float interactDistance = 2.0f;

    void Awake()
    {
        inventory = GetComponent<Inventory>();
        agentState = GetComponent<AgentState>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 解析目標名稱 (Server 應該傳來 {"name": "Hamburger"} 或 {"id": "Hamburger"})
        string targetName = "";
        if (args.ContainsKey("name")) targetName = args["name"].ToString();
        else if (args.ContainsKey("id")) targetName = args["id"].ToString();

        if (string.IsNullOrEmpty(targetName))
        {
            ReportError("沒有指定要撿什麼東西 (缺少 name 參數)");
            return;
        }

        // 2. 在場景中尋找該物件
        // (為了簡單起見，我們先用 Find，之後可以改用 AgentPerception 的快取清單)
        GameObject targetObj = GameObject.Find(targetName);

        if (targetObj == null)
        {
            ReportError($"找不到名為 '{targetName}' 的物件");
            return;
        }

        // 3. 檢查距離 (模擬 ActionController 的 Raycast 距離限制)
        float dist = 0f;
    
        // 1. 嘗試抓取目標的碰撞器 (Collider)
        Collider targetCol = targetObj.GetComponent<Collider>();
        
        if (targetCol != null)
        {
            // 關鍵魔法：找出目標表面離我最近的那個點
            Vector3 closestPoint = targetCol.ClosestPoint(transform.position);
            dist = Vector3.Distance(transform.position, closestPoint);
        }
        else
        {
            // 如果目標沒有 Collider，只好算中心點 (退步做法)
            dist = Vector3.Distance(transform.position, targetObj.transform.position);
        }

        // --- 這樣你的 interactDistance 只要設 1.5 甚至 1.0 就夠了！ ---
        if (dist > interactDistance) 
        {
            string errorMsg = $"目標太遠了 (邊緣距離: {dist:F1}m)，請先靠近";
            Debug.LogWarning($"[ActionPut] {errorMsg}");
            agentState.ReportActionFinished(false, errorMsg);
            return;
        }
        Vector3 targetPostion = targetObj.transform.position;
        targetPostion.y = transform.position.y; // 鎖定 Y 軸，避免狗狗抬頭看天
        transform.LookAt(targetPostion);
        // 4. 執行撿取邏輯 (整合原本的 Inventory 系統)
        // 檢查目標有沒有 ItemBox 元件 (這是你原本 ActionController 裡的判斷邏輯)
        if (targetObj.TryGetComponent<ItemBox>(out ItemBox itemBox))
        {
            // A. 從 ItemBox 拿到物品類型 (ItemType)
            ItemType itemType = itemBox.GetItem();

            // B. 呼叫 Inventory 執行撿取
            inventory.TakeItem(itemType);

            // C. 成功回報
            Debug.Log($"[ActionPickup] 成功撿起: {targetName} (類型: {itemType})");
            agentState.SetHeldItem(targetName); // 更新 AI 的記憶
            agentState.ReportActionFinished(true, $"Picked up {targetName}");

            // D. 處理場景上的物件
            // 注意：Inventory.TakeItem 只是顯示手上的東西，場景地板上的東西通常要隱藏或銷毀
            // 如果 ItemBox 腳本裡沒有處理銷毀，我們要在這裡處理
            //targetObj.SetActive(false); 
        }
        else
        {
            ReportError($"物件 '{targetName}' 上面沒有 ItemBox 元件，無法撿取！");
        }
    }

    private void ReportError(string errorMsg)
    {
        Debug.LogError($"[ActionPickup] 失敗: {errorMsg}");
        agentState.ReportActionFinished(false, errorMsg);
    }
    [ContextMenu("測試：撿起 Hamburger")]
    public void TestPickup()
    {
        var args = new Dictionary<string, object> { { "name", "BreadBox" } };
        Execute(args);
    }
}