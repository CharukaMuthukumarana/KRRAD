import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. Load the Big Data (Same file used for Deep Learning)
print("Loading Big Dataset (final_training_data.csv)...")
df = pd.read_csv('ml_engine/data/final_training_data.csv')

# Features: [PPS, Bytes, Packets, Avg_Packet_Size]
X = df.drop(columns=['Label'])
y = df['Label']

# 2. Train Random Forest (The "Fast Expert")
print("Training Random Forest on full dataset...")
rf_model = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42)
rf_model.fit(X, y)
print("✅ Random Forest Trained.")

# 3. Train Isolation Forest (The "Anomaly Hunter")
# We train ONLY on benign traffic to teach it what "Normal" looks like
print("Training Isolation Forest on Normal traffic...")
normal_traffic = X[y == 0]
iso_model = IsolationForest(n_estimators=100, contamination=0.01, random_state=42, n_jobs=-1)
iso_model.fit(normal_traffic)
print("✅ Isolation Forest Trained.")

# 4. Save Models
joblib.dump(rf_model, 'ml_engine/models/rf_model_big.pkl')
joblib.dump(iso_model, 'ml_engine/models/iso_model_big.pkl')
print("🚀 All models saved to ml_engine/models/")