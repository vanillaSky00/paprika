using UnityEngine;
using System.Collections.Generic;

[RequireComponent(typeof(AgentState))]
[RequireComponent(typeof(Inventory))]
[RequireComponent(typeof(AgentNetworkManager))] // 🔥 確保有 Manager
public class ActionPut : MonoBehaviour, IAgentAction
{
    public string ActionName => "put_down";

    private AgentState agentState;
    private Inventory inventory;
    private AgentNetworkManager networkManager; // 🔥 1. 新增變數

    // 設定最大互動距離 (例如 2.5 公尺)
    [SerializeField] private float interactDistance = 2.0f;

    void Awake() // 改用 Awake 確保初始化順序
    {
        agentState = GetComponent<AgentState>();
        inventory = GetComponent<Inventory>();
        networkManager = GetComponent<AgentNetworkManager>(); // 🔥 2. 抓取元件
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 檢查手上是不是空的
        if (inventory.CurrentType == ItemType.NONE)
        {
            string msg = "Hand is empty";
            Debug.LogWarning("[ActionPut] 手上沒東西，無法放下！");
            
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Self", false, msg);
            
            agentState.ReportActionFinished(false, msg);
            return;
        }

        // 2. 找出目標桌子
        if (!args.ContainsKey("id")) 
        { 
            string msg = "Missing 'id' argument";
            Debug.LogError("沒指定放哪"); 
            
            // 🔥 紀錄失敗 (並回報結束以免卡死)
            if (networkManager) networkManager.RecordActionTrace(ActionName, "Unknown", false, msg);
            agentState.ReportActionFinished(false, msg);
            return; 
        }

        string targetId = args["id"].ToString();
        
        GameObject targetObj = SmartObjectFinder.FindBestTarget(targetId, transform.position);
        
        if (targetObj != null)
        {
            // --- 新增：距離檢查 ---
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

            // --- 距離判斷 ---
            if (dist > interactDistance) 
            {
                string errorMsg = $"目標太遠了 (邊緣距離: {dist:F1}m)，請先靠近";
                Debug.LogWarning($"[ActionPut] {errorMsg}");
                
                // 🔥 紀錄失敗
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, errorMsg);
                
                agentState.ReportActionFinished(false, errorMsg);
                return;
            }

            // --- 新增：面對桌子 (視覺優化) ---
            Vector3 targetPostion = targetObj.transform.position;
            targetPostion.y = transform.position.y; // 鎖定 Y 軸，避免狗狗抬頭看天
            transform.LookAt(targetPostion);

            // --- 原本的放置邏輯 (IPutItemFull) ---
            if (targetObj.TryGetComponent<IPutItemFull>(out IPutItemFull itemPutBox))
            {
                bool success = itemPutBox.PutItem(inventory.CurrentType);

                if (success)
                {
                    string msg = $"Put item on {targetId}";
                    inventory.ClearHand();
                    agentState.DropObject();

                    Debug.Log($"[ActionPut] 成功把 {inventory.CurrentType} 放在 {targetId}");
                    
                    // 🔥 紀錄成功
                    if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, true, msg);
                    
                    agentState.ReportActionFinished(true, msg);
                }
                else
                {
                    string msg = "Target refused item (Full?)";
                    Debug.LogWarning($"[ActionPut] {targetId} 拒絕接收 (可能是滿了)");
                    
                    // 🔥 紀錄失敗
                    if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
                    
                    agentState.ReportActionFinished(false, "Target refused item");
                }
            }
            else
            {
                string msg = "Target cannot hold items (No IPutItemFull)";
                Debug.LogError($"[ActionPut] 目標 {targetId} 不能放東西");
                
                // 🔥 紀錄失敗
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
                
                agentState.ReportActionFinished(false, "Target cannot hold items");
            }
        }
        else
        {
            string msg = $"Target container '{targetId}' not found";
            Debug.LogError($"[ActionPut] {msg}");
            
            // 🔥 紀錄失敗
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);
            
            agentState.ReportActionFinished(false, "Target container not found");
        }
    }
}