| Node                                 | Requires Input (Read)                                                                                                     | Produces Record (Write)                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Curriculum Node <br> (The Strategist)** | **STM:** reads `recent_tasks` to avoid repeating. <br> **LTM:** reads episodic memories to recall “what happened here before?” | **None** (consumes memory to decide next task)                                                   |
| **Skill Node <br> (The Librarian)**       | **LTM:** queries Vector DB for procedural skills matching the current task                                                | **None** (retrieves info)                                                                        |
| **Action Node <br> (The Body)**           | **LTM:** receives `skill_guide` (procedural) from Skill Node. <br> **STM:** reads `last_plan` + `critique` if retrying         | **STM (implicit):** outputs a `plan` that lives in graph state as working memory                 |
| **Critic Node <br> (The Judge)**          | **None** (judges Reality vs Goal; no history needed)                                                                      | **None**                                                                                         |
| **Learning Node <br> (The Scribe)**       | **None**                                                                                                                  | **LTM:** writes new skills (procedural) to DB. **STM:** updates `recent_tasks` (episodic buffer) |






