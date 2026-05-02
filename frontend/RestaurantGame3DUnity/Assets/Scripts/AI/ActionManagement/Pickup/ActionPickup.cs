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
        // Prefer the plain ItemBox base class when there are multiple
        // ItemBox-derived components on the target (Table/TableBox
        // override GetItem() to return NONE unless certain state
        // conditions are met — picking from a container that is
        // conceptually a "box of tomatoes" should always yield the box's
        // stored item, not a state-guarded override).
        ItemBox itemBox = PickIngredientBox(targetObj);
        if (itemBox != null)
        {
            ItemType itemType = itemBox.GetItem();
            Debug.Log($"[ActionPickup] {targetName} → {itemBox.GetType().Name} on '{itemBox.gameObject.name}' returned {itemType}");

            // 檢查箱子給的東西是不是 NONE
            if (itemType == ItemType.NONE)
            {
                string msg = $"[ActionPickup] Failed: {targetName} ({itemBox.GetType().Name}) is empty or cool down!";
                Debug.LogWarning(msg);

                // 🔥 紀錄失敗
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            if (!inventory.TakeItem(itemType))
            {
                string msg = $"Hands full — already holding {inventory.CurrentType}. Put it down first.";
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            Debug.Log($"[ActionPickup] 成功從箱子撿起: {itemType}");
            
            // 🔥 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, true, $"Picked up {itemType}");

            agentState.SetHeldItem(itemType.ToString());
            agentState.ReportActionFinished(true, $"Picked up {itemType}");
            return;
        }

        // --- 情況 B: 從砧板 (SliceBoard) 拿取 ---
        SliceBoard board = targetObj.GetComponent<SliceBoard>() ?? targetObj.GetComponentInChildren<SliceBoard>();
        if (board != null)
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
            if (!inventory.TakeItem(itemOnBoard))
            {
                string msg = $"Hands full — already holding {inventory.CurrentType}. Put it down first.";
                if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, msg);

                agentState.ReportActionFinished(false, msg);
                return;
            }

            board.ClearObject(); // 拿走後要清空砧板

            Debug.Log($"[ActionPickup] 成功從砧板拿走: {itemOnBoard}");
            
            // 🔥 紀錄成功
            if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, true, $"Picked up {itemOnBoard}");

            agentState.SetHeldItem(itemOnBoard.ToString());
            agentState.ReportActionFinished(true, $"Picked up {itemOnBoard}");
            return;
        }

        string error = $"物件 '{targetName}' 上沒有 ItemBox 或 SliceBoard 元件，無法撿取！";
        Debug.LogError($"[ActionPickup] {error}");

        // 🔥 紀錄失敗
        if (networkManager) networkManager.RecordActionTrace(ActionName, targetName, false, error);

        agentState.ReportActionFinished(false, error);
    }

    // Picks the right ItemBox on / under the target. Preference order:
    //   1. A plain ItemBox on the target itself (ingredient crates).
    //   2. Any other ItemBox-derived component on the target (Oven, Table).
    //   3. The same preference walked into children.
    // This avoids a subtle bug where `GetComponent<ItemBox>()` on a
    // target hosting Table + plain ItemBox returns whichever was added
    // first — Table.GetItem() returns NONE in most states, making the
    // crate look empty even when it holds an ingredient.
    private static ItemBox PickIngredientBox(GameObject target)
    {
        if (target == null) return null;

        ItemBox[] onSelf = target.GetComponents<ItemBox>();
        ItemBox plain = FirstPlainItemBox(onSelf);
        if (plain != null) return plain;
        if (onSelf.Length > 0) return onSelf[0];

        ItemBox[] inChildren = target.GetComponentsInChildren<ItemBox>(includeInactive: false);
        ItemBox plainChild = FirstPlainItemBox(inChildren);
        if (plainChild != null) return plainChild;
        return inChildren.Length > 0 ? inChildren[0] : null;
    }

    private static ItemBox FirstPlainItemBox(ItemBox[] candidates)
    {
        foreach (var c in candidates)
        {
            if (c != null && c.GetType() == typeof(ItemBox))
                return c;
        }
        return null;
    }
}