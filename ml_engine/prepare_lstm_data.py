# ml_engine/prepare_lstm_data.py
import pandas as pd
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import joblib

# CONFIG
SEQUENCE_LENGTH = 10  # Look back at the last 10 readings

def create_sequences(data, seq_length):
    xs, ys = [], []
    data_values = data.drop(columns=['Label']).values
    labels = data['Label'].values
    
    for i in range(len(data) - seq_length):
        x = data_values[i:(i + seq_length)]
        y = labels[i + seq_length] # Predict the label of the *next* step
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def run():
    print("Loading data for LSTM sequence generation...")
    # Load the augmented data (Real + Noise) we made earlier
    df = pd.read_csv('ml_engine/data/augmented_data.csv')
    
    # Normalize Features (Deep Learning NEEDS 0-1 scaling)
    scaler = MinMaxScaler()
    feature_cols = ['Flow Duration', 'Total Fwd Packets', 'Total Backward Packets', 'Flow Bytes/s', 'Flow Packets/s']
    df[feature_cols] = scaler.fit_transform(df[feature_cols])
    
    # Save the scaler (Controller needs it to scale live data)
    joblib.dump(scaler, 'ml_engine/models/scaler.pkl')
    print("Scaler saved.")

    # Create Sequences
    print(f"Creating {SEQUENCE_LENGTH}-step sequences...")
    X, y = create_sequences(df, SEQUENCE_LENGTH)
    
    # Save as PyTorch tensors
    torch.save(torch.from_numpy(X).float(), 'ml_engine/data/lstm_X.pt')
    torch.save(torch.from_numpy(y).float(), 'ml_engine/data/lstm_y.pt')
    print(f"LSTM Data Ready: {X.shape}")

if __name__ == "__main__":
    run()