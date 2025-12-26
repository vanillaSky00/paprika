using System.Collections.Generic;
public interface IAgentAction {
    string ActionName { get; }
    void Execute(Dictionary<string, object> args);
}