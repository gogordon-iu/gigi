import json
from Zhennan.llm_client_azure import LLMClient
from coordinator import ActivityCoordinator

def test_coordinator():
    client = LLMClient()
    coordinator = ActivityCoordinator(client)
    
    plan = {
        "activity_title": "Test Activity",
        "approximate_duration": "5 minutes"
    }
    
    step = {
        "goal": "Have a conversation about space.",
        "step_type": "open"
    }

    # Case 1: Inappropriate behavior
    history_behavior = [
        {"role": "assistant", "content": "Hi! Do you like stars?"},
        {"role": "user", "content": "No, you are a stupid robot and I hate you."}
    ]
    print("\n--- Testing Inappropriate Behavior ---")
    res = coordinator.check_intervention(history_behavior, plan, step, 1.0)
    print(json.dumps(res, indent=2))

    # Case 2: Student question
    history_question = [
        {"role": "assistant", "content": "What's your favorite planet?"},
        {"role": "user", "content": "I like Mars. By the way, how many moons does Jupiter have?"}
    ]
    print("\n--- Testing Student Question ---")
    res = coordinator.check_intervention(history_question, plan, step, 2.0)
    print(json.dumps(res, indent=2))

    # Case 3: Time control (near end)
    history_time = [
        {"role": "assistant", "content": "Space is so cool."},
        {"role": "user", "content": "Yeah I love it."}
    ]
    print("\n--- Testing Time Control (Near End) ---")
    res = coordinator.check_intervention(history_time, plan, step, 4.8)
    print(json.dumps(res, indent=2))

    # Case 4: Time control (over time)
    print("\n--- Testing Time Control (Over Time) ---")
    res = coordinator.check_intervention(history_time, plan, step, 6.0)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    test_coordinator()
