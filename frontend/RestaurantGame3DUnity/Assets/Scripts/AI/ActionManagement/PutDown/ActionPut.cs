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
                ItemType heldItem = inventory.CurrentType;

                // Capture assembly state BEFORE put_down so we can describe
                // the stack transition / rejection with precise context.
                Table assemblyTable = ResolveAssemblyTable(targetObj);
                bool wasAssemblySurface = assemblyTable != null && assemblyTable.IsAssemblySurface;
                ItemType expectedLayer = wasAssemblySurface
                    ? assemblyTable.NextExpectedAssemblyType
                    : ItemType.NONE;

                bool success = itemPutBox.PutItem(heldItem);

                if (success)
                {
                    inventory.ClearHand();
                    agentState.DropObject();

                    string msg = BuildPutSuccessMessage(targetId, heldItem, assemblyTable, wasAssemblySurface);
                    Debug.Log($"[ActionPut] 成功把 {heldItem} 放在 {targetId}");

                    if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, true, msg);

                    agentState.ReportActionFinished(true, msg);
                }
                else
                {
                    string msg = BuildPutFailureMessage(targetId, heldItem, assemblyTable, wasAssemblySurface, expectedLayer);
                    Debug.LogWarning($"[ActionPut] {targetId} 拒絕接收: {msg}");

                    if (networkManager) networkManager.RecordActionTrace(ActionName, targetId, false, msg);

                    agentState.ReportActionFinished(false, msg);
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

    // Resolves the underlying Table hosting the burger plate, whether the
    // LLM pointed `put_down` at the Table directly or at a TableBox wrapper.
    private static Table ResolveAssemblyTable(GameObject target)
    {
        if (target == null) return null;
        Table direct = target.GetComponent<Table>();
        if (direct != null) return direct;
        TableBox box = target.GetComponent<TableBox>();
        return box != null ? box.table : null;
    }

    private static string BuildPutSuccessMessage(
        string targetId,
        ItemType heldItem,
        Table assemblyTable,
        bool wasAssemblySurface)
    {
        if (wasAssemblySurface && assemblyTable != null)
        {
            int placed = assemblyTable.AssemblyStack.Count;
            int total = assemblyTable.IsAssemblyDone
                ? placed
                : placed + (assemblyTable.NextExpectedAssemblyType == ItemType.NONE ? 0 : 1);
            string progress = total > 0 ? $"{placed}/{total}" : placed.ToString();

            if (assemblyTable.IsAssemblyDone)
                return $"Stacked {heldItem} on {targetId} — burger COMPLETE ({progress}).";

            ItemType next = assemblyTable.NextExpectedAssemblyType;
            string nextHint = next != ItemType.NONE ? $" Next expected: {next}." : "";
            return $"Stacked {heldItem} on {targetId} (plate {progress}).{nextHint}";
        }
        return $"Put {heldItem} on {targetId}";
    }

    private static string BuildPutFailureMessage(
        string targetId,
        ItemType heldItem,
        Table assemblyTable,
        bool wasAssemblySurface,
        ItemType expectedLayer)
    {
        if (wasAssemblySurface && assemblyTable != null)
        {
            if (assemblyTable.IsAssemblyDone)
                return $"{targetId} plate is COMPLETE — pick up the finished burger instead of stacking more.";
            if (expectedLayer != ItemType.NONE && expectedLayer != heldItem)
                return $"{targetId} plate rejected {heldItem} — next expected layer is {expectedLayer}.";
            return $"{targetId} plate rejected {heldItem}.";
        }
        return $"{targetId} is already occupied — pick a different table.";
    }
}