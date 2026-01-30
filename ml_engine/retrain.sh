#!/bin/bash
echo "1. Extracting recent normal traffic logs..."
# (In a real system, this pulls from a database. Here we simulate.)
python3 -c "import pandas as pd; df=pd.read_csv('ml_engine/data/augmented_data.csv'); df.to_csv('ml_engine/data/current_traffic.csv', index=False)"

echo "2. Retraining Models on new data..."
python3 ml_engine/train_model.py

echo "3. Redeploying Brain..."
kubectl delete pod -l app=krrad-controller
echo "System has adapted to new patterns."