using System;
using System.Collections.Generic;
using UnityEngine;

namespace Paprika.AI
{
    [Serializable]
    public class WorldObjectDTO {
        public string id;
        public string type;
        public Vector3 position;
        public float distance;
        public string state;
    }

    [Serializable]
    public class PerceptionDTO {
        public int time_hour;
        public int day;
        public string mode = "reality";
        public string location_id;
        public List<WorldObjectDTO> nearby_objects = new List<WorldObjectDTO>();
        public string held_item;
    }

    [Serializable]
    public class AgentActionDTO {
        public string function;
        public Dictionary<string, object> args;
        public bool plan_complete;
    }

    [Serializable]
    public class AgentResponseDTO {
        public string client_id;
        public string task;
        public List<AgentActionDTO> plan;
    }
}