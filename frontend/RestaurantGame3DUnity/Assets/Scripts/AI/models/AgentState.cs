using UnityEngine;

public class AgentState : MonoBehaviour
{
    [ContextMenu("測試：假裝撿到蘋果")]
    public void TestPickupApple()
    {
        SetHeldItem("Apple");
        Debug.Log("測試指令已執行：Agent 現在手上有 Apple");
    }

    [ContextMenu("測試：顯示當前狀態")]
    public void PrintStatus()
    {
        Debug.Log($"[AgentState 檢查] 地點: {currentLocationId}, 手持: {currentHeldItem}");
    }
    
    [Header("Status")]
    [SerializeField] private string currentLocationId = "Unknown";
    [SerializeField] private string currentHeldItem = null;
    [SerializeField] private string lastActionStatus = "none";
    [SerializeField] private string lastActionError = null;
    public GameObject heldObj;
    public bool IsActionExecuting { get; set; } = false;

    public string GetLocationId()
    {
        // 這裡可以結合 Trigger 偵測，或者直接回傳變數
        return currentLocationId;
    }

    public string GetHeldItem()
    {
        return currentHeldItem;
    }

    public void GetLastActionStatus(out string status, out string error)
    {
        status = lastActionStatus;
        error = lastActionError;
    }

    // --- 供動作腳本 (ActionController) 呼叫的方法 ---

    public void SetLocation(string locationName)
    {
        currentLocationId = locationName;
    }

    public void SetHeldItem(string itemName)
    {
        currentHeldItem = itemName;
    }
    public void PickupObject(GameObject obj)
    {
        heldObj = obj;
        currentHeldItem = obj.name;
    }
    public void DropObject()
    {
        heldObj = null;
        currentHeldItem = null;
    }
    public void ReportActionFinished(bool success, string errorMessage = null)
    {
        lastActionStatus = success ? "success" : "failure";
        lastActionError = errorMessage;
        IsActionExecuting = false;
    }
}