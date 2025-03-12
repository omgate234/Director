import json

# Load JSON data from file
with open("evaluation_results.json", "r") as file:
    evaluations = json.load(file)

# Prepare the Markdown table header
markdown_table = """| Session ID | Conv ID | Gemini 1 Avg | Gemini 0.7 Avg | Gemini 0.5 Avg | Best Model | At Par or Better |
|------------|--------|-------------|---------------|-------------|------------|------------------|
"""

# Process each evaluation entry
for entry in evaluations:
    session_id = entry["session_id"]
    conv_id = entry["conv_id"]

    def compute_avg(model):
        values = entry["output"][model].values()
        return round(sum(values) / len(values), 2)

    gemini_1_avg = compute_avg("gemini_1")
    gemini_0_7_avg = compute_avg("gemini_0_7")
    gemini_0_5_avg = compute_avg("gemini_0_5")

    best_model = entry["output"]["best_model"]
    at_par = "✅" if entry["output"]["at_par_or_better_than_existing"] else "❌"

    # Append row to table
    markdown_table += f"| {session_id} | {conv_id} | {gemini_1_avg} | {gemini_0_7_avg} | {gemini_0_5_avg} | {best_model} | {at_par} |\n"

# Save to file
with open("evaluation.txt", "w") as output_file:
    output_file.write(markdown_table)

print("Markdown table saved to evaluation.txt")
