using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Table : ItemBox, IPutItemFull
{
    [SerializeField] private List<ObjectnType> itemsToHold = new List<ObjectnType>();
    [SerializeField] private Plate plate;
    [SerializeField] private bool isFull; 

    private void Start()
    {
        SetType(ItemType.NONE);
    }
    public override ItemType GetItem()
    {
        if (GetCurrentType() == ItemType.PLATE && plate.isDone == false) { return ItemType.NONE; }
        else if (plate.isDone)
        {  
            StartCoroutine(ChangeType());
            plate.ResetPlate();
            return ItemType.HAMBURGER;
        }
        else if (isFull)
        {  
            StartCoroutine(ChangeType());
            return base.GetItem();
        }
        return ItemType.NONE;
    }
    
    public bool PutItem(ItemType item)
    {  
        if (!isFull)
        {
            SetType(item);
            foreach (ObjectnType itemHold in itemsToHold)
            {
                if (itemHold.type != GetCurrentType())
                {
                    itemHold.item.SetActive(false);
                }
                else
                {
                    itemHold.item.SetActive(true);
                }
            }
            StartCoroutine(PutCoolDown());
            return true;
        }
        else
        {
            if (GetCurrentType() == ItemType.PLATE)
            {
                if(item != ItemType.PLATE)
                {
                    StartCoroutine(PutCoolDown());
                    return plate.PutItem(item);
                } 
            }
        }
        return false;
    } 

    public float GetAssemblyProgress()
    {
        if (plate == null) return 0f;
        return plate.Progress;
    }

    public bool HasAssemblyPlate()
    {
        return GetCurrentType() == ItemType.PLATE || plate != null;
    }

    // `IsAssemblySurface` is the canonical "this table is the burger plate"
    // signal that the network layer and ActionPut use to decide whether
    // failure of a put_down means "wrong layer" vs "table already occupied".
    public bool IsAssemblySurface => GetCurrentType() == ItemType.PLATE && plate != null;

    public ItemType NextExpectedAssemblyType =>
        plate != null ? plate.NextExpectedType : ItemType.NONE;

    public List<ItemType> AssemblyStack =>
        plate != null ? plate.PlacedStack : new List<ItemType>();

    public bool IsAssemblyDone => plate != null && plate.isDone;
    private IEnumerator PutCoolDown()
    {
        yield return new WaitForEndOfFrame();
        isFull = true;
    }
    private IEnumerator ChangeType()
    {
        CloseItem();
        yield return new WaitForEndOfFrame();
        SetType(ItemType.NONE);
        isFull = false;
    }
    public void CloseItem()
    {
        itemsToHold.ForEach(item => item.item.SetActive(false)); 
    }
}
