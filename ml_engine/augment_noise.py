# ml_engine/augment_noise.py
import pandas as pd
import numpy as np

def generate_noise_data(n_samples=5000):
    print(f"Generating {n_samples} samples of 'Idle/Background' traffic...")
    
    # Simulate very low traffic (0 to 100 packets/sec)
    # Features: [Flow Duration, Total Fwd Packets, Total Bwd Packets, Flow Bytes/s, Flow Packets/s, Label]
    
    # Duration: Short checks (0.01s to 1.0s)
    duration = np.random.uniform(0.01, 1.0, n_samples)
    
    # Packets: Very few (1 to 5 packets)
    fwd_pkts = np.random.randint(1, 5, n_samples)
    bwd_pkts = np.random.randint(0, 5, n_samples)
    
    # Rates: Low
    pkts_sec = np.random.uniform(0, 100, n_samples) # 0 to 100 PPS
    bytes_sec = pkts_sec * np.random.uniform(60, 100, n_samples) # Small packets
    
    df_noise = pd.DataFrame({
        'Flow Duration': duration,
        'Total Fwd Packets': fwd_pkts,
        'Total Backward Packets': bwd_pkts,
        'Flow Bytes/s': bytes_sec,
        'Flow Packets/s': pkts_sec,
        'Label': 0 # DEFINITELY NORMAL
    })
    
    return df_noise

def augment_and_save():
    # 1. Load Real Data
    try:
        real_df = pd.read_csv('ml_engine/data/processed_data.csv')
        print(f"Loaded Real Data: {real_df.shape}")
        
        # Calculate how many noise samples we need to balance the dataset
        n_real = len(real_df)
        print(f"Generating {n_real} noise samples to balance classes 50/50...")
        
    except:
        print("Real data not found.")
        return

    # 2. Generate Noise (EQUAL TO REAL DATA SIZE)
    noise_df = generate_noise_data(n_samples=n_real) 
    
    # 3. Combine
    combined_df = pd.concat([real_df, noise_df], ignore_index=True)
    
    # 4. Shuffle
    combined_df = combined_df.sample(frac=1).reset_index(drop=True)
    
    # 5. Save
    combined_df.to_csv('ml_engine/data/augmented_data.csv', index=False)
    print(f"Success! Saved balanced dataset with {combined_df.shape[0]} rows.")

if __name__ == "__main__":
    augment_and_save()