using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace Paprika.AI
{
    public class AgentClient : MonoBehaviour
    {
        private WebSocket websocket;
        public string serverUrl = "ws://localhost:8000/api/ws/agent/player_1";
        
        // Reference to our execution script
        [SerializeField] private ActionDispatcher dispatcher;

        async void Start()
        {
            websocket = new WebSocket(serverUrl);

            websocket.OnOpen += () => Debug.Log("<color=green>AI Brain Connected!</color>");
            websocket.OnError += (e) => Debug.LogError("AI Error: " + e);
            websocket.OnClose += (c) => Debug.Log("AI Connection Closed.");

            websocket.OnMessage += (bytes) =>
            {
                string json = System.Text.Encoding.UTF8.GetString(bytes);
                var response = JsonConvert.DeserializeObject<AgentResponseDTO>(json);
                
                if (response != null && response.plan != null)
                {
                    dispatcher.ExecutePlan(response.plan);
                }
            };

            await websocket.Connect();
        }

        void Update()
        {
            #if !UNITY_WEBGL || UNITY_EDITOR
                websocket.DispatchMessageQueue();
            #endif
        }

        public async void SendPerception(PerceptionDTO perception)
        {
            if (websocket.State == WebSocketState.Open)
            {
                string json = JsonConvert.SerializeObject(perception);
                await websocket.SendText(json);
            }
        }

        private async void OnApplicationQuit()
        {
            if (websocket != null) await websocket.Close();
        }
    }
}