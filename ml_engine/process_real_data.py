# ml_engine/process_real_data.py
import pandas as pd
import numpy as np
import glob
import os

# 1. Configuration
RAW_DATA_PATH = 'ml_engine/raw_data/*.csv'
OUTPUT_PATH = 'ml_engine/data/processed_data.csv'
SAMPLE_RATE = 0.1  # Load 10% of each file to prevent Memory Error

# 2. Define Features compatible with our eBPF capabilities
# We only select features that correspond to "Count" and "Rate"
# which our eBPF sensor can easily provide.
KEEP_COLUMNS = [
    'Flow Duration', 
    'Total Fwd Packets', 
    'Total Backward Packets', 
    'Flow Bytes/s', 
    'Flow Packets/s', 
    'Label'
]

def load_and_process():
    all_files = glob.glob(RAW_DATA_PATH)
    if not all_files:
        print("Error: No CSV files found in ml_engine/raw_data/")
        return

    df_list = []
    
    print(f"Found {len(all_files)} files. Processing...")

    for filename in all_files:
        print(f" - Loading {os.path.basename(filename)}...")
        # Read only a subset to save RAM
        try:
            # We skip bad lines to avoid parser errors common in this dataset
            df_chunk = pd.read_csv(filename, nrows=50000) 
            df_list.append(df_chunk)
        except Exception as e:
            print(f"   Skipping {filename}: {e}")

    # Combine all chunks
    df = pd.concat(df_list, ignore_index=True)
    print(f"Total raw records: {len(df)}")

    # 3. Cleaning
    # Strip whitespace from column names (Critical for CIC dataset)
    df.columns = df.columns.str.strip()

    # Rename 'Total Bwd Packets' to match standard naming if needed
    # (CIC sometimes mixes 'Total Backward Packets' vs 'Total Bwd Packets')
    if 'Total Bwd Packets' in df.columns:
        df.rename(columns={'Total Bwd Packets': 'Total Backward Packets'}, inplace=True)

    # Filter to only the columns we want
    # Check if columns exist before selecting
    available_cols = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df[available_cols]

    # Handle Infinity and NaNs
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)

    # 4. Encoding Labels
    # The dataset has labels like "DrDoS_DNS", "BENIGN".
    # We map BENIGN -> 0, Everything else -> 1 (Attack)
    df['Label'] = df['Label'].apply(lambda x: 0 if x == 'BENIGN' else 1)

    # 5. Save
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Success! Processed data saved to {OUTPUT_PATH}")
    print(f"Final shape: {df.shape}")
    print(df['Label'].value_counts())

if __name__ == "__main__":
    load_and_process()