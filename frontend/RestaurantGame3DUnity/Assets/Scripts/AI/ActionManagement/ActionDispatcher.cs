using UnityEngine;
using System.Collections.Generic;

public class ActionDispatcher : MonoBehaviour
{
    private Dictionary<string, IAgentAction> actions = new Dictionary<string, IAgentAction>();

    void Awake()
    {
        // 自動搜尋身上所有掛載的動作腳本
        var foundActions = GetComponents<IAgentAction>();
        foreach (var action in foundActions)
        {
            if (!actions.ContainsKey(action.ActionName))
            {
                actions.Add(action.ActionName, action);
            }
        }
    }

    public void DispatchAction(string functionName, Dictionary<string, object> args)
    {
        if (actions.ContainsKey(functionName))
        {
            Debug.Log($"[ActionDispatcher] 執行動作: {functionName}");
            actions[functionName].Execute(args);
        }
        else
        {
            Debug.LogWarning($"[ActionDispatcher] 找不到動作: {functionName}");
        }
    }
}