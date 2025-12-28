using System.Collections;
using System.Collections.Generic;
using UnityEngine;
 
public class SliceBoard : Functionality,IPutItemFull
{
    [SerializeField] private List<ObjectnType> itemsToHold = new List<ObjectnType>();
    private ItemType currentType; 
    public ItemType CurrentType => currentType;
    private void Start()
    {
        currentType = ItemType.NONE;
        timer.gameObject.SetActive(false);
    }
    public override ItemType Process()
    {
        if (currentType == ItemType.NONE) return ItemType.NONE;
        if (processStarted == true && timer.gameObject.activeSelf == false)
        {
            timer.gameObject.SetActive(true);
        }
        processStarted = true;
        currentTime += Time.deltaTime;
        timer.UpdateClock(currentTime, maxTime);
        if (currentTime >= maxTime)
        {
            currentTime = 0;
            timer.gameObject.SetActive(false);
            processStarted = false;
            timer.UpdateClock(currentTime, maxTime);
            switch (currentType)
            {
                case ItemType.TOMATO: 
                    return ItemType.SLICEDTOM;
                case ItemType.LETTUCE:  
                    return ItemType.SLICEDLET;
                case ItemType.ONION: 
                    return ItemType.SLICEDON;
                case ItemType.CHEESE: 
                    return ItemType.SLICEDCHE;
                case ItemType.BREAD:
                    return ItemType.SLICEDBREAD;
            }
        }
        return ItemType.NONE;
    }
    public override void ClearObject()
    {
        base.ClearObject();
        currentType = ItemType.NONE;
        itemsToHold.ForEach(obj => obj.item.SetActive(false));
    }
    public bool PutItem(ItemType item)
    {
        if (FilterItem(item)==false) return false;
        if (currentType != ItemType.NONE) return false;
        currentType = item;
        foreach (ObjectnType itemHold in itemsToHold)
        {
            if (itemHold.type != currentType)
            {
                itemHold.item.SetActive(false);
            }
            else
            {
                itemHold.item.SetActive(true);
            }
        }
        this.currentType = item;
        return true;
    } 
    private bool FilterItem(ItemType type)
    { 
        switch (type)
        {
            // --- 原料 (原本就有的) ---
            case ItemType.TOMATO:
            case ItemType.LETTUCE:
            case ItemType.ONION:
            case ItemType.CHEESE:
            case ItemType.BREAD:
            case ItemType.MEATBALL: // 如果有的話

            // --- 必須補上這些！不然切完放不回去！ ---
            case ItemType.SLICEDTOM:
            case ItemType.SLICEDLET:
            case ItemType.SLICEDON:
            case ItemType.SLICEDCHE:
            case ItemType.SLICEDBREAD:
            case ItemType.COOKEDMEAT: // 如果有熟肉的話
            case ItemType.HAMBURGER:  // 如果會在桌上組裝的話
                return true;

            default:
                return false; 
        } 
    }
}
