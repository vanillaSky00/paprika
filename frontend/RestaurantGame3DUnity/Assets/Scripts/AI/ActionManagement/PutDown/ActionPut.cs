using UnityEngine;
using System.Collections.Generic;

public class ActionPut : MonoBehaviour, IAgentAction
{
    public string ActionName => "put_down";

    private AgentState agentState;
    private Inventory inventory;

    // 設定最大互動距離 (例如 2.5 公尺)
    [SerializeField] private float interactDistance = 2.0f;

    void Start()
    {
        agentState = GetComponent<AgentState>();
        inventory = GetComponent<Inventory>();
    }

    public void Execute(Dictionary<string, object> args)
    {
        // 1. 檢查手上是不是空的
        if (inventory.CurrentType == ItemType.NONE)
        {
            Debug.LogWarning("[ActionPut] 手上沒東西，無法放下！");
            agentState.ReportActionFinished(false, "Hand is empty");
            return;
        }

        // 2. 找出目標桌子
        if (!args.ContainsKey("id")) 
        { 
            Debug.LogError("沒指定放哪"); 
            return; 
        }

        string targetId = args["id"].ToString();
        ///GameObject targetObj = GameObject.Find(targetId);
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

            // --- 這樣你的 interactDistance 只要設 1.5 甚至 1.0 就夠了！ ---
            if (dist > interactDistance) 
            {
                string errorMsg = $"目標太遠了 (邊緣距離: {dist:F1}m)，請先靠近";
                Debug.LogWarning($"[ActionPut] {errorMsg}");
                agentState.ReportActionFinished(false, errorMsg);
                return;
            }

            // --- 新增：面對桌子 (視覺優化) ---
            // 讓狗狗轉向桌子，才不會背對著桌子放東西
            Vector3 targetPostion = targetObj.transform.position;
            targetPostion.y = transform.position.y; // 鎖定 Y 軸，避免狗狗抬頭看天
            transform.LookAt(targetPostion);

            // --- 原本的放置邏輯 (IPutItemFull) ---
            if (targetObj.TryGetComponent<IPutItemFull>(out IPutItemFull itemPutBox))
            {
                bool success = itemPutBox.PutItem(inventory.CurrentType);

                if (success)
                {
                    inventory.ClearHand();
                    agentState.DropObject();

                    Debug.Log($"[ActionPut] 成功把 {inventory.CurrentType} 放在 {targetId}");
                    agentState.ReportActionFinished(true, $"Put item on {targetId}");
                }
                else
                {
                    Debug.LogWarning($"[ActionPut] {targetId} 拒絕接收 (可能是滿了)");
                    agentState.ReportActionFinished(false, "Target refused item");
                }
            }
            else
            {
                Debug.LogError($"[ActionPut] 目標 {targetId} 不能放東西 (沒繼承 IPutItemFull)");
                agentState.ReportActionFinished(false, "Target cannot hold items");
            }
        }
        else
        {
            Debug.LogError($"[ActionPut] 找不到桌子: {targetId}");
            agentState.ReportActionFinished(false, "Target container not found");
        }
    }
}