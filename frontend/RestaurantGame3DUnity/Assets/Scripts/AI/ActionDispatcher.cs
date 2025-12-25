using UnityEngine;
using System.Collections.Generic;
using Paprika.AI;

public class ActionDispatcher : MonoBehaviour
{
    [Header("Player Components")]
    public MovementController movement;
    public ActionController actionController;
    public Inventory inventory;

    public void ExecutePlan(List<AgentActionDTO> plan)
    {
        foreach (var action in plan)
        {
            Debug.Log($"AI Command: {action.function}");

            switch (action.function)
            {
                case "interact":
                    // Calls DoAction from your uploaded ActionController.cs
                    actionController.SendMessage("DoAction"); 
                    break;
                
                case "clear_hand":
                    // Accesses method from your uploaded Inventory.cs
                    inventory.ClearHand();
                    break;

                case "say":
                    if (action.args.ContainsKey("text"))
                        Debug.Log($"<color=cyan>Agent says: {action.args["text"]}</color>");
                    break;
            }
        }
    }
}