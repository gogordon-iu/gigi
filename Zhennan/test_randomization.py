from strategy_catalog import StrategyCatalog

def test_randomization():
    catalog = StrategyCatalog()
    
    # Get total strategies
    total_strategies = len(catalog.get_all_strategies())
    print(f"Total strategies in catalog: {total_strategies}")
    
    # Get grouped counts
    groups = {}
    for s in catalog.strategies:
        if s.trigger_group:
            groups[s.trigger_group] = groups.get(s.trigger_group, 0) + 1
    
    print(f"Groups: {groups}")
    
    # Run randomization multiple times and check for differences
    outputs = set()
    for i in range(100):
        output = catalog.get_randomized_catalog_string()
        outputs.add(output)
    
    print(f"Unique catalog outputs after 100 runs: {len(outputs)}")
    
    if len(outputs) > 1:
        print("SUCCESS: Randomization is working (multiple unique outputs found).")
    else:
        print("FAILURE: Randomization yielded only one unique output.")

    # Check that each output contains exactly one member from each group
    # We can check the number of strategies in the output
    # Expected number = (total - grouped_total) + number_of_groups
    grouped_total = sum(groups.values())
    expected_count = (total_strategies - grouped_total) + len(groups)
    
    output = catalog.get_randomized_catalog_string()
    # Counting "- ID:" occurrences as a proxy for strategy count
    actual_count = output.count("- ID:")
    
    print(f"Expected strategy count per randomized output: {expected_count}")
    print(f"Actual strategy count in sample output: {actual_count}")
    
    if expected_count == actual_count:
        print("SUCCESS: Count matches expected.")
    else:
        print("FAILURE: Count does NOT match expected.")

if __name__ == "__main__":
    test_randomization()
