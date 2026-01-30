import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. Load Data
print("Loading Data...")
df = pd.read_csv('ml_engine/data/augmented_data.csv')

# --- MODEL 1: RANDOM FOREST (The Specialist) ---
print("Training Random Forest (Attack Classifier)...")
X = df.drop(columns=['Label'])
y = df['Label']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)
preds = rf_model.predict(X_test)
print(f"RF Accuracy: {accuracy_score(y_test, preds)}")

# --- MODEL 2: ISOLATION FOREST (The Anomaly Hunter) ---
silence_df = pd.DataFrame(0, index=range(5000), columns=df.columns)
silence_df['Label'] = 0 # Mark as Safe

# We train ONLY on "Benign" (Normal) traffic to teach it what 'Normal' looks like
normal_traffic = df[df['Label'] == 0]
training_data = pd.concat([normal_traffic, silence_df], ignore_index=True).drop(columns=['Label'])

print("Training Isolation Forest (with Silence Baseline)...")
# Reduced contamination to 0.01 (1%) so it trusts almost everything as normal
iso_forest = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
iso_forest.fit(training_data)

# 3. Save Both Models
joblib.dump(rf_model, 'ml_engine/models/traffic_classifier.pkl')
joblib.dump(iso_forest, 'ml_engine/models/anomaly_detector.pkl')
print("SUCCESS: Saved 'traffic_classifier.pkl' and 'anomaly_detector.pkl'")