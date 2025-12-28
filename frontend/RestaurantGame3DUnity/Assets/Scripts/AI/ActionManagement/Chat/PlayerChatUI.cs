using UnityEngine;
using UnityEngine.UI;
using TMPro; // 如果你用 TextMeshPro，沒用的話改用 InputField

public class PlayerChatUI : MonoBehaviour
{
    [Header("References")]
    public AgentNetworkManager networkManager;
    public TMP_InputField inputField; // 如果是舊版 UI，改用 public InputField inputField;
    public Button sendButton;

    void Start()
    {
        // 綁定按鈕事件
        sendButton.onClick.AddListener(SendMessageToAgent);

        // 綁定 Enter 鍵事件 (UX 優化)
        inputField.onSubmit.AddListener(delegate { SendMessageToAgent(); });
    }

    void Update()
    {
        // 按下 Enter 也可以發送，並重新聚焦輸入框
        if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
        {
            if(inputField.isFocused && !string.IsNullOrEmpty(inputField.text))
            {
                SendMessageToAgent();
            }
            else
            {
                // 如果沒聚焦，按 Enter 自動聚焦
                inputField.ActivateInputField();
            }
        }
    }

    void SendMessageToAgent()
    {
        if (string.IsNullOrEmpty(inputField.text)) return;
        if (networkManager == null) return;

        string msg = inputField.text;
        
        // 呼叫 Manager 的中斷函式
        networkManager.ReceivePlayerMessage(msg);

        // 清空輸入框
        inputField.text = "";
        
        // 保持輸入框焦點 (可選，看你喜好)
        // inputField.ActivateInputField(); 
    }
}