using UnityEngine;

public class AgentState : MonoBehaviour
{
    [Header("Status")]
    [SerializeField] private string currentLocationId = "Unknown";
    [SerializeField] private string currentHeldItem = null;
    [SerializeField] private string lastActionStatus = "none";
    [SerializeField] private string lastActionError = null;

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

    public void ReportActionFinished(bool success, string errorMessage = null)
    {
        lastActionStatus = success ? "success" : "failure";
        lastActionError = errorMessage;
    }
}