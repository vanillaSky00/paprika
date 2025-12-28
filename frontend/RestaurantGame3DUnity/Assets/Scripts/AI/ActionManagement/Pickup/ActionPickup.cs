using UnityEngine;
using System.Collections.Generic;

[RequireComponent(typeof(Inventory))]
[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(AgentNetworkManager))] // 🔥 確保有 Manager
public class ActionPickup : MonoBehaviour, IAgentAction
{
    public string ActionName => "pickup";

    private Inventory inventory;
    private AgentState agentState;
    private AgentNetworkManager networkManager; // 🔥 1. 新增變數
    
    [SerializeField] private float interactDistance = 2.5f;

    void Awake()
    {
        inventory = GetComponent<Inventory>();
        agentState = GetComponent<AgentState>();
        networkManager = GetComponent<AgentNetworkManager>(); // 🔥 2. 抓取元件
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 參數檢查
        string targetName = "";
        if (args.ContainsKey("name")) targetName = args["name"].ToString();
        else if (args.ContainsKey("id")) targetName = args["id"].ToString();

        if (string.IsNullOrEmpty(targetName))
        {
            string msg = "Missing 'id' or 'name'";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Unknown", false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 2. 尋找物件
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetName, transform.position);
        if (targetObj == null) targetObj = GameObject.Find(targetName); // 備案

        if (targetObj == null)
        {
            string msg = $"Object '{targetName}' not found";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 3. 距離檢查
        float dist = Vector3.Distance(transform.position, targetObj.transform.position);
        if (dist > interactDistance)
        {
            string msg = $"Too far from {targetName} ({dist:F1}m)";
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 4. 執行撿取 (邏輯核心)
        
        // --- 情況 A: 從食材箱 (ItemBox) 拿取 ---
        if (targetObj.TryGetComponent<ItemBox>(out ItemBox itemBox))
        {
            ItemType itemType = itemBox.GetItem();

            // 檢查箱子給的東西是不是 NONE
            if (itemType == ItemType.NONE)
            {
                string msg = $"[ActionPickup] Failed: {targetName} (ItemBox) is empty or cool down!";
                Debug.LogWarning(msg);
                
                // 🔥 紀錄失敗
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            inventory.TakeItem(itemType);
            
            // 雙重檢查：確認 Inventory 真的拿到了
            if (inventory.CurrentType == ItemType.NONE)
            {
                string msg = "Inventory failed to take item (Hand might be full?)";
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            Debug.Log($"[ActionPickup] 成功從箱子撿起: {itemType}");
            
            // 🔥 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, true, $"Picked up {itemType}");

            agentState.SetHeldItem(itemType.ToString());
            agentState.ReportActionFinished(true, $"Picked up {itemType}");
        }
        // --- 情況 B: 從砧板 (SliceBoard) 拿取 ---
        else if (targetObj.TryGetComponent<SliceBoard>(out SliceBoard board))
        {   
            if (board.CurrentType == ItemType.NONE)
            {
                string msg = $"The board {targetName} is empty!";
                // 🔥 紀錄失敗
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            ItemType itemOnBoard = board.CurrentType;
            inventory.TakeItem(itemOnBoard);
            
            board.ClearObject(); // 拿走後要清空砧板

            Debug.Log($"[ActionPickup] 成功從砧板拿走: {itemOnBoard}");
            
            // 🔥 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, true, $"Picked up {itemOnBoard}");

            agentState.SetHeldItem(itemOnBoard.ToString());
            agentState.ReportActionFinished(true, $"Picked up {itemOnBoard}");
        }
        else
        {
            // 嘗試找子物件 (以防腳本掛在子層級)
            var childBox = targetObj.GetComponentInChildren<ItemBox>();
            if(childBox != null)
            {
                 string msg = $"Found ItemBox on child of {targetName}, logic needs refinement.";
                 if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);
                 agentState.ReportActionFinished(false, msg);
                 return;
            }

            string error = $"物件 '{targetName}' 上沒有 ItemBox 或 SliceBoard 元件，無法撿取！";
            Debug.LogError($"[ActionPickup] {error}");
            
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, error);

            agentState.ReportActionFinished(false, error);
        }
    }
}