using System.Collections;
using System.Collections.Generic;
using UnityEngine;


public class Plate : MonoBehaviour
{
    [SerializeField] private List<ObjectnType> objects = new List<ObjectnType>();
    [SerializeField]private int currentObjectIndex = 0;
    public bool isDone = false;
    public int CurrentObjectIndex => currentObjectIndex;
    public int TotalSteps => objects.Count;
    public float Progress => objects.Count == 0 ? 0f : (float)currentObjectIndex / objects.Count;

    // Scene serialization can leave currentObjectIndex non-zero; without
    // this reset the first stack attempt after load matches some mid-stack
    // slot instead of the bread layer and every put_down is rejected.
    private void Start()
    {
        ResetPlate();
    }

    public ItemType NextExpectedType =>
        (currentObjectIndex < 0 || currentObjectIndex >= objects.Count)
            ? ItemType.NONE
            : objects[currentObjectIndex].type;

    public List<ItemType> PlacedStack
    {
        get
        {
            var list = new List<ItemType>(currentObjectIndex);
            for (int i = 0; i < currentObjectIndex && i < objects.Count; i++)
                list.Add(objects[i].type);
            return list;
        }
    }

    public bool PutItem(ItemType type)
    {
        if (currentObjectIndex > objects.Count-1) return false;
        if (type == objects[currentObjectIndex].type)
        {
            objects[currentObjectIndex].item.SetActive(true);
            currentObjectIndex++;
            if(currentObjectIndex > objects.Count - 1)
            {
                isDone = true;
            }
            return true;
        }
        return false;
    }
    public void ResetPlate()
    {
        isDone = false;
        currentObjectIndex = 0;
        foreach(ObjectnType obj in objects)
        {
            obj.item.SetActive(false);
        }
    }
}
