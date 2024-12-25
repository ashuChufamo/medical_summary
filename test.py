import pandas as pd
import re
from collections import Counter

# Load the Excel file and extract test details
file_path = 'Medication and Lab data Nov 2024.xlsx'

# Load the second sheet (Lab Order)
sheet_name = 'Lab Order'  # Update this if the sheet name differs
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Function to extract all test names (nested or flat) from the "Test Result" column
def extract_tests(test_result):
    """
    Extracts all individual tests from a nested string like:
    '{Chemistry: {RTF: Urea, Creatinine}, Hematology: CBC}'
    """
    tests = []
    if isinstance(test_result, str):  # Ensure it's a valid string
        # Use regex to capture both keys and values inside the nested format
        matches = re.findall(r'([\w\s]+):|([\w\s]+)(?=[,}])', test_result)
        for key, value in matches:
            if key:  # Top-level key/category
                tests.append(key.strip())
            if value:  # Nested values/test names
                tests.append(value.strip())
    return tests

# Extract and count all unique tests
all_tests = []
for result in df['Test Result']:
    all_tests.extend(extract_tests(result))

# Count the occurrences of each test
test_counts = Counter(all_tests)

# Display the unique tests and their counts
print("Different Tests and Their Counts:")
for test, count in test_counts.items():
    print(f"{test}: {count}")

# Save results to a CSV file (optional)
output_path = 'test_counts_summary.csv'
pd.DataFrame(test_counts.items(), columns=['Test', 'Count']).to_csv(output_path, index=False)
print(f"\nSummary saved to {output_path}")
