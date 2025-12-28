using UnityEngine;
using TMPro; // 記得引用

public class AgentThoughtBubble : MonoBehaviour
{
    [Header("UI References")]
    public Canvas bubbleCanvas;
    public TMP_Text thoughtText;
    public GameObject backgroundPanel; // 背景圖 (Image)

    [Header("Settings")]
    public float hideDelay = 5.0f; // 幾秒後自動消失
    private float timer = 0;
    private Camera mainCamera;
    public float heightOffset = 0.5f;
    public Transform targetAgent;
    void Start()
    {
        mainCamera = Camera.main;
        // 一開始先隱藏
        if(bubbleCanvas) bubbleCanvas.enabled = false;
    }

    void LateUpdate() // 使用 LateUpdate 確保在相機移動後才轉向
    {
        // --- 1. Billboard 效果 (永遠面向攝影機) ---
        if (bubbleCanvas.enabled && mainCamera != null)
        {
            transform.position = targetAgent.position + Vector3.up * heightOffset;
            // 讓 Canvas 的正面朝向攝影機
            transform.rotation = mainCamera.transform.rotation;
        }
        
        // --- 2. 自動隱藏計時 ---
        if (timer > 0)
        {
            timer -= Time.deltaTime;
            if (timer <= 0)
            {
                HideBubble();
            }
        }
    }

    // 公開函式：讓外部呼叫來顯示文字
    public void ShowThought(string text)
    {
        if (bubbleCanvas == null) return;

        thoughtText.text = text;
        bubbleCanvas.enabled = true;
        if(backgroundPanel) backgroundPanel.SetActive(true);

        // 重置計時器
        timer = hideDelay;
    }

    public void HideBubble()
    {
        if (bubbleCanvas) bubbleCanvas.enabled = false;
    }
}