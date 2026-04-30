import pandas as pd

FORM_CSV_PATH = "form_responses_test.csv"

df = pd.read_csv(FORM_CSV_PATH)

print("Loaded form response CSV successfully.")
print(f"Number of rows: {len(df)}")

print("\nColumns found:")
for col in df.columns:
    print(f"- {col}")

print("\nFirst few rows:")
print(df.head())
